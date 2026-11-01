#!/usr/bin/env python3
"""Add every book in a folder to the library (phases 1-4) from the command line.

Books added here show up in the website too - both use toyota_rag/library.py.
Files already in the library (same content) are skipped, so re-running is free.

  python ingest.py                     # all files in data/books (download_books.py fills it)
  python ingest.py --dir my_books/     # any folder with .pdf / .docx / .md / .txt
  python ingest.py --reset             # empty the library and the vector database first
  python ingest.py --dry-run           # only extract + chunk, print statistics (no API key needed)
"""

import argparse
import json
from pathlib import Path

from toyota_rag import config
from toyota_rag.chunking import chunk_documents
from toyota_rag.loaders import SUPPORTED, load_directory


def dry_run(folder):
    docs = load_directory(folder)
    chunks = chunk_documents(docs, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    sizes = [len(c.text) for c in chunks]
    print(f"\n{len(docs)} sections -> {len(chunks)} chunks "
          f"(min {min(sizes)}, avg {sum(sizes) / len(sizes):.0f}, max {max(sizes)} characters)")
    print(f"Embedding them will take about {-(-len(chunks) // config.EMBEDDING_BATCH_SIZE)} OpenRouter requests.")
    sample = chunks[len(chunks) // 2]
    print(f"\nExample chunk: {sample.id}\nmetadata: {sample.metadata}\n---\n{sample.text}")


def main(folder: Path, reset: bool):
    from toyota_rag.embeddings import OpenRouterEmbedder
    from toyota_rag.library import Library
    from toyota_rag.vectorstores import ChromaStore

    store = ChromaStore()
    library = Library(OpenRouterEmbedder(), store)
    if reset:
        library.clear()
        store.reset()

    catalog = json.loads((folder / "sources.json").read_text(encoding="utf-8")) \
        if (folder / "sources.json").exists() else {}
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in SUPPORTED)
    if not files:
        raise SystemExit(f"No .pdf/.docx/.md/.txt files in {folder}. Run `python download_books.py` first.")

    for f in files:
        info = catalog.get(f.name, {})
        print(f"  {f.name:<48}", end=" ", flush=True)
        book = library.add(f.name, f.read_bytes(), info.get("title"), info.get("url"), wait=True)
        if book.get("duplicate"):
            print("already in the library")
        elif book["status"] == "ready":
            print(f"{book['chunks']:>4} chunks, {book['requests']} requests")
        else:
            print(f"ERROR {book['error']}")
    print(f"\nLibrary: {len(library.ready_ids())} books ready, {store.count()} chunks in ChromaDB. "
          "Start the website with: python app.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", type=Path, default=config.DATA_DIR, help="folder with books (default data/books)")
    p.add_argument("--reset", action="store_true", help="remove all books first")
    p.add_argument("--dry-run", action="store_true", help="only extract + chunk, print statistics")
    args = p.parse_args()
    dry_run(args.dir) if args.dry_run else main(args.dir, args.reset)
