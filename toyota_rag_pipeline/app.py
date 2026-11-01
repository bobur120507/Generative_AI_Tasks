#!/usr/bin/env python3
"""Web site: upload a book (PDF / DOCX / MD / TXT), let it be processed, then chat with it.

  python app.py                  # http://127.0.0.1:5000
  python app.py --port 8000 --host 0.0.0.0

REST API (used by static/app.js, also usable with curl):
  GET    /api/status              settings, whether the API key is set, counts
  GET    /api/books               all books with status / progress / statistics
  POST   /api/books               upload one or more files (multipart field "file", optional "title")
  GET    /api/books/<id>          one book incl. chunk lengths and a preview of the first chunks
  POST   /api/books/<id>/retry    process a failed book again
  DELETE /api/books/<id>          delete the book, its file and its vectors
  POST   /api/ask                 {"question": "...", "book_ids": [...], "k": 4} -> answer + sources
"""

import argparse

from flask import Flask, jsonify, render_template, request

from toyota_rag import config
from toyota_rag.library import UploadError

MAX_QUESTION_CHARS = 2000
LIGHT_FIELDS = ("chunk_lengths", "preview")   # left out of the book list to keep polling cheap


def create_app(library=None, rag=None):
    """Build the Flask app. Tests pass in a library/rag with fake models; normally real ones are created."""
    if library is None or rag is None:
        from toyota_rag.embeddings import OpenRouterEmbedder
        from toyota_rag.library import Library
        from toyota_rag.rag import ToyotaRAG
        from toyota_rag.vectorstores import ChromaStore

        embedder, store = OpenRouterEmbedder(), ChromaStore()
        library = library or Library(embedder, store)
        rag = rag or ToyotaRAG(embedder, store)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = int((config.MAX_UPLOAD_MB * 5 + 1) * 1024 * 1024)  # up to 5 files at once

    def light(book):
        return {k: v for k, v in book.items() if k not in LIGHT_FIELDS}

    @app.get("/")
    def index():
        return render_template("index.html", max_mb=int(config.MAX_UPLOAD_MB))

    @app.get("/api/status")
    def status():
        books = library.list()
        return jsonify(
            api_key=bool(config.OPENROUTER_API_KEY), embedding_model=config.EMBEDDING_MODEL,
            chat_models=config.CHAT_MODELS, max_upload_mb=config.MAX_UPLOAD_MB,
            supported=[".pdf", ".docx", ".md", ".txt"], chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP, top_k=config.TOP_K,
            books_ready=sum(b["status"] == "ready" for b in books),
            chunks=sum(b["chunks"] for b in books if b["status"] == "ready"),
        )

    @app.get("/api/books")
    def list_books():
        return jsonify(books=[light(b) for b in library.list()])

    @app.post("/api/books")
    def upload():
        files = request.files.getlist("file")
        if not files:
            return jsonify(error="Fayl tanlanmagan."), 400
        title = request.form.get("title") or None
        added, errors = [], []
        for f in files:
            try:
                book = library.add(f.filename or "file", f.read(), title=title if len(files) == 1 else None)
                added.append(light(book))
            except UploadError as exc:
                errors.append({"filename": f.filename, "error": str(exc)})
        return jsonify(books=added, errors=errors), (202 if added else 400)

    @app.get("/api/books/<book_id>")
    def book_detail(book_id):
        book = library.get(book_id)
        return (jsonify(book), 200) if book else (jsonify(error="Kitob topilmadi."), 404)

    @app.post("/api/books/<book_id>/retry")
    def retry(book_id):
        book = library.retry(book_id)
        return (jsonify(light(book)), 202) if book else (jsonify(error="Kitob topilmadi."), 404)

    @app.delete("/api/books/<book_id>")
    def delete(book_id):
        return (jsonify(deleted=book_id), 200) if library.delete(book_id) else (jsonify(error="Kitob topilmadi."), 404)

    @app.post("/api/ask")
    def ask():
        data = request.get_json(silent=True) or {}
        question = str(data.get("question", "")).strip()
        if not question:
            return jsonify(error="Savol bo‘sh."), 400
        if len(question) > MAX_QUESTION_CHARS:
            return jsonify(error=f"Savol juda uzun (ko‘pi bilan {MAX_QUESTION_CHARS} belgi)."), 400
        ready = library.ready_ids()
        book_ids = [b for b in (data.get("book_ids") or ready) if b in ready]
        if not book_ids:
            return jsonify(error="Hali tayyor kitob yo‘q. Avval kitob yuklang va qayta ishlanishini kuting."), 409
        k = max(1, min(int(data.get("k") or config.TOP_K), 10))
        try:
            answer, model, results = rag.ask(question, k=k, book_ids=book_ids)
        except config.MissingKeyError as exc:
            return jsonify(error=str(exc)), 503
        except Exception as exc:
            return jsonify(error=f"Model javob bermadi: {exc}"), 502
        return jsonify(answer=answer, model=model, sources=[{
            "n": i, "book_id": r.metadata.get("book_id"), "book": r.metadata.get("source_book"),
            "citation": r.citation(), "url": r.url(), "score": round(r.score, 4), "text": r.text,
        } for i, r in enumerate(results, start=1)])

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error=f"Fayl juda katta (chegara {config.MAX_UPLOAD_MB:.0f} MB)."), 413

    return app


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()
    if not config.OPENROUTER_API_KEY:
        print("! OPENROUTER_API_KEY is not set - the site opens, but processing and answers will fail.")
    print(f"Open http://{args.host}:{args.port} in your browser")
    create_app().run(host=args.host, port=args.port, debug=False, threaded=True)
