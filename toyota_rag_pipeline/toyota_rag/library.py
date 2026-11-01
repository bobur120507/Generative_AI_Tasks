"""The book library: upload -> extract -> chunk -> embed -> store.

Used by both the website (app.py) and the command line (ingest.py).

* Every book gets an id = first 12 hex chars of the SHA-256 of its bytes, so
  uploading the same file twice does not create a duplicate.
* Processing runs in ONE background worker thread: the web page stays
  responsive, and books are embedded one after another, which respects the
  free OpenRouter rate limit (20 requests/minute).
* The catalog (title, status, progress, statistics) is saved in
  data/library/library.json, the original files in data/library/files/.

Status of a book:  queued -> extracting -> embedding -> ready   (or -> error)
"""

import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config
from .chunking import chunk_documents
from .loaders import SUPPORTED, load_file

FILE_SIGNATURES = {".pdf": b"%PDF", ".docx": b"PK"}   # a .docx is a zip archive
BUSY = ("queued", "extracting", "embedding")


class UploadError(ValueError):
    """Problem with the uploaded file itself (shown to the user as a 400 error)."""


class Library:
    def __init__(self, embedder, store, root=config.LIBRARY_DIR, chunk_size=config.CHUNK_SIZE,
                 chunk_overlap=config.CHUNK_OVERLAP, max_mb=config.MAX_UPLOAD_MB,
                 batch_size=config.EMBEDDING_BATCH_SIZE):
        self.embedder, self.store = embedder, store
        self.root = Path(root)
        self.files_dir = self.root / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.root / "library.json"
        self.chunk_size, self.chunk_overlap = chunk_size, chunk_overlap
        self.max_bytes = int(max_mb * 1024 * 1024)
        self.batch_size = batch_size
        self._lock = threading.RLock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="book-worker")
        self.books = json.loads(self.catalog_path.read_text(encoding="utf-8")) if self.catalog_path.exists() else {}
        for book_id, book in self.books.items():   # the server stopped while these were being processed
            if book["status"] in BUSY:
                self._submit(book_id)

    # ------------------------------------------------------------------ catalog helpers
    def _save(self):
        tmp = self.catalog_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.books, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.catalog_path)   # atomic: never leaves a half-written file

    def _update(self, book_id, **fields):
        with self._lock:
            if book_id in self.books:
                self.books[book_id].update(fields)
                self._save()

    def list(self):
        with self._lock:
            return sorted((dict(b) for b in self.books.values()), key=lambda b: b["uploaded_at"], reverse=True)

    def get(self, book_id):
        with self._lock:
            book = self.books.get(book_id)
            return dict(book) if book else None

    def ready_ids(self):
        with self._lock:
            return [i for i, b in self.books.items() if b["status"] == "ready"]

    # ------------------------------------------------------------------ public actions
    def add(self, filename: str, data: bytes, title: str | None = None, url: str | None = None,
            wait: bool = False) -> dict:
        """Validate and save an uploaded file, then queue it for processing."""
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED:
            raise UploadError(f"Bu fayl turi qo‘llab-quvvatlanmaydi: {ext or '(kengaytmasiz)'}. "
                              f"Ruxsat etilgan: {', '.join(sorted(SUPPORTED))}")
        if not data:
            raise UploadError("Fayl bo‘sh.")
        if len(data) > self.max_bytes:
            raise UploadError(f"Fayl juda katta: {len(data) / 1e6:.1f} MB (chegara {self.max_bytes / 1e6:.0f} MB).")
        if ext in FILE_SIGNATURES and not data.startswith(FILE_SIGNATURES[ext]):
            raise UploadError(f"Fayl ichidagi ma’lumot {ext} formatiga mos emas (fayl buzilgan bo‘lishi mumkin).")

        book_id = hashlib.sha256(data).hexdigest()[:12]
        with self._lock:
            existing = self.books.get(book_id)
            if existing and existing["status"] != "error":
                return {**existing, "duplicate": True}
            (self.files_dir / f"{book_id}{ext}").write_bytes(data)
            self.books[book_id] = {
                "id": book_id, "filename": Path(filename).name, "file_type": ext.lstrip("."),
                "size_bytes": len(data), "title": (title or "").strip() or None, "url": url,
                "status": "queued", "progress": 0, "error": None,
                "uploaded_at": time.time(), "finished_at": None,
                "chapters": 0, "chunks": 0, "characters": 0, "requests": 0,
                "chunk_lengths": [], "preview": [],
            }
            self._save()
            entry = dict(self.books[book_id])
        future = self._submit(book_id)
        if wait:
            future.result()
            return self.get(book_id)
        return entry

    def retry(self, book_id):
        book = self.get(book_id)
        if not book:
            return None
        if book["status"] not in BUSY:
            self._update(book_id, status="queued", error=None, progress=0)
            self._submit(book_id)
        return self.get(book_id)

    def delete(self, book_id) -> bool:
        with self._lock:
            book = self.books.pop(book_id, None)
            if not book:
                return False
            self._save()
        self.store.delete({"book_id": book_id})
        (self.files_dir / f"{book_id}.{book['file_type']}").unlink(missing_ok=True)
        return True

    def clear(self):
        for book_id in list(self.books):
            self.delete(book_id)

    def wait_idle(self, timeout=60):
        """Block until every queued book is processed (used by tests and ingest.py)."""
        end = time.time() + timeout
        while any(b["status"] in BUSY for b in self.list()) and time.time() < end:
            time.sleep(0.05)

    # ------------------------------------------------------------------ processing pipeline
    def _submit(self, book_id):
        return self._worker.submit(self._process, book_id)

    def _process(self, book_id):
        book = self.get(book_id)
        if not book:
            return
        try:
            # Phase 1: extract text + split into chapters
            self._update(book_id, status="extracting", progress=5)
            path = self.files_dir / f"{book_id}.{book['file_type']}"
            docs = load_file(path, book["title"], book["url"])
            if not docs or not any(d.text.strip() for d in docs):
                raise UploadError("Fayldan matn ajratib olinmadi. Agar bu skanerlangan PDF bo‘lsa, avval OCR qiling.")
            for d in docs:
                d.metadata.update(book_id=book_id, source_file=book["filename"])
            title = book["title"] or docs[0].metadata["source_book"]

            # Phase 2: chunk with overlap; ids are prefixed with the book id so books never collide
            chunks = chunk_documents(docs, self.chunk_size, self.chunk_overlap)
            for c in chunks:
                c.id = f"{book_id}-{c.id}"
                c.metadata["source_book"] = title
            self._update(book_id, title=title, status="embedding", progress=10, chapters=len(docs),
                         chunks=len(chunks), characters=sum(len(d.text) for d in docs),
                         chunk_lengths=[len(c.text) for c in chunks],
                         preview=[{"id": c.id, "chapter": c.metadata["chapter_title"], "text": c.text[:500]}
                                  for c in chunks[:3]])

            # Phases 3-4: embed in batches (1 request each) and store; skip chunks stored earlier
            stored = self.store.existing_texts([c.id for c in chunks])
            todo = [c for c in chunks if stored.get(c.id) != c.text]
            batches = math.ceil(len(todo) / self.batch_size)
            for n in range(batches):
                batch = todo[n * self.batch_size:(n + 1) * self.batch_size]
                vectors = self.embedder.embed_documents([c.embedding_text for c in batch])
                self.store.upsert([c.id for c in batch], vectors, [c.text for c in batch],
                                  [c.metadata for c in batch])
                self._update(book_id, progress=10 + int(90 * (n + 1) / batches), requests=n + 1)
            self._update(book_id, status="ready", progress=100, finished_at=time.time())
        except Exception as exc:
            self._update(book_id, status="error", error=f"{type(exc).__name__}: {exc}")
