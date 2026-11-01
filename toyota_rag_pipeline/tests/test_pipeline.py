"""Offline tests - no API key, no internet.

A TF-IDF embedder and an in-memory store stand in for the OpenRouter embedding
model and ChromaDB; a fake client stands in for the OpenRouter chat API.
Run:  python -m pytest -q
"""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluate import evaluate  # noqa: E402
from toyota_rag.chunking import RecursiveOverlapSplitter, chunk_documents  # noqa: E402
from toyota_rag.cleaning import clean_text, is_page_number, remove_headers_footers  # noqa: E402
from toyota_rag.embeddings import OpenRouterEmbedder  # noqa: E402
from toyota_rag.loaders import load_directory, load_pdf, load_text, parse_chapter_heading  # noqa: E402
from toyota_rag.library import Library, UploadError  # noqa: E402
from toyota_rag.rag import ToyotaRAG, build_prompt  # noqa: E402
from toyota_rag.vectorstores import MemoryStore  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
DATA = FIXTURES / "sample_books"   # small offline corpus; real books live in data/books
CASES = json.loads((FIXTURES / "sample_questions.json").read_text(encoding="utf-8"))


class TfidfEmbedder:
    model = "tfidf-test"

    def __init__(self, corpus):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2)).fit(corpus)

    def embed_documents(self, texts):
        return self.vec.transform(texts).toarray().tolist()

    embed_queries = embed_documents

    def embed_query(self, text):
        return self.embed_queries([text])[0]


class FakeOpenRouter:
    """Mimics openai.OpenAI(base_url=openrouter): .chat.completions.create and .embeddings.create."""

    def __init__(self, fail_models=(), reject_input_type=False):
        self.fail_models, self.reject_input_type = set(fail_models), reject_input_type
        self.chat_calls, self.embed_calls = [], []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._embed)

    def _chat(self, **kw):
        self.chat_calls.append(kw)
        if kw["model"] in self.fail_models:
            raise RuntimeError("model unavailable")
        msg = SimpleNamespace(content="Just-in-time means making only what is needed [1].")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def _embed(self, **kw):
        self.embed_calls.append(kw)
        if self.reject_input_type and "input_type" in kw.get("extra_body", {}):
            err = RuntimeError("bad request")
            err.status_code = 400
            raise err
        data = [SimpleNamespace(index=i, embedding=[float(len(t)), 1.0]) for i, t in enumerate(kw["input"])]
        return SimpleNamespace(data=list(reversed(data)))  # out of order on purpose


@pytest.fixture(scope="module")
def chunks():
    return chunk_documents(load_directory(DATA, verbose=False), 800, 150)


def make_library(root, embedder, store=None, **kw):
    return Library(embedder, store or MemoryStore(), root=root, chunk_size=800, chunk_overlap=150,
                   batch_size=16, **kw)


def add_fixture_books(library):
    """Upload the 4 sample books exactly like the website does (bytes + file name)."""
    return [library.add(f.name, f.read_bytes(), wait=True) for f in sorted(DATA.glob("*.md"))]


@pytest.fixture(scope="module")
def rag(chunks, tmp_path_factory):
    embedder = TfidfEmbedder([c.embedding_text for c in chunks])
    library = make_library(tmp_path_factory.mktemp("lib"), embedder)
    add_fixture_books(library)
    rag = ToyotaRAG(embedder, library.store, client=FakeOpenRouter(), models=["model-a:free", "model-b:free"])
    rag.library = library
    return rag


# ---------------------------------------------------------------- Phase 1: loading & cleaning

def test_page_numbers():
    for line in ["12", "Page 12", " - 47 - ", "12 of 300", "xiv", "iv"]:
        assert is_page_number(line), line
    for line in ["1. Overproduction", "Chapter 3", "mix", "In 1937 Toyota"]:
        assert not is_page_number(line), line


def test_clean_text():
    out = clean_text("The ﬁrst Toyota pro-\nduction line used\nkanban cards.\n\n17\n\nNext para­ graph.")
    assert "first Toyota production line used kanban cards." in out
    assert "17" not in out and "­" not in out


def test_headers_and_footers_removed():
    topics = ["kaizen", "jidoka", "kanban", "heijunka", "andon", "muda", "takt", "gemba"]
    pages = [f"THE TOYOTA WAY\nThis page explains {t}.\nMore on {t}.\nChapter Notes {i}\n{i}"
             for i, t in enumerate(topics, start=1)]
    cleaned = [clean_text(p) for p in remove_headers_footers(pages)]
    assert all("THE TOYOTA WAY" not in p and "Chapter Notes" not in p for p in cleaned)
    assert all("This page explains" in p for p in cleaned)


def test_chapter_heading():
    assert parse_chapter_heading("Chapter 3: Just-In-Time") == (3, "Just-In-Time")
    assert parse_chapter_heading("CHAPTER 12") == (12, "Chapter 12")
    assert parse_chapter_heading("This chapter explains") is None


def test_markdown_corpus():
    docs = load_directory(DATA, verbose=False)
    assert {d.metadata["source_book"] for d in docs} == {
        "Toyota Production System Handbook", "The Toyota Way - Principles and Culture",
        "Toyota Corporate History", "Toyota Hybrid System and Powertrain Technology"}
    tps = [d for d in docs if d.metadata["source_book"] == "Toyota Production System Handbook"]
    assert [d.metadata["chapter"] for d in tps] == list(range(1, 9))
    assert tps[2].metadata["chapter_title"] == "Just-In-Time"
    assert not any("**" in d.text or d.text.startswith("#") for d in docs)


def test_txt_loader(tmp_path):
    f = tmp_path / "toyota_notes.txt"
    f.write_text("Preface.\n\nCHAPTER 1: Looms\nSakichi built\nlooms.\n\n3\n\nChapter 2 - Cars\nKiichiro built cars.")
    docs = load_text(f)
    assert [(d.metadata["chapter"], d.metadata["chapter_title"]) for d in docs] == [
        (0, "Front matter"), (1, "Looms"), (2, "Cars")]
    assert docs[1].text == "Sakichi built looms." and docs[0].metadata["source_book"] == "Toyota Notes"


def test_pdf_loader(tmp_path):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    path = tmp_path / "lean_book.pdf"
    c = canvas.Canvas(str(path))
    c.setTitle("Lean Thinking at Toyota")
    pages = {1: ["Chapter 1: Flow", "One-piece flow exposes problems quickly."],
             2: ["Work moves between steps without waiting."],
             3: ["Chapter 2: Pull", "Kanban cards signal the upstream process."],
             4: ["The supermarket is restocked as parts are removed."]}
    for n, lines in pages.items():
        c.drawString(72, 800, "LEAN THINKING AT TOYOTA")
        for j, line in enumerate(lines):
            c.drawString(72, 700 - 20 * j, line)
        c.drawString(300, 40, str(n))
        c.showPage()
    c.save()

    docs = load_pdf(path)
    assert docs[0].metadata["source_book"] == "Lean Thinking at Toyota"
    assert [(d.metadata["chapter"], d.metadata["page_start"], d.metadata["page_end"]) for d in docs] == [
        (1, 1, 2), (2, 3, 4)]
    assert "LEAN THINKING" not in " ".join(d.text for d in docs)


# ---------------------------------------------------------------- Phase 2: chunking

def test_chunk_size_ids_metadata(chunks):
    assert len(chunks) > 40 and all(len(c.text) <= 800 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)
    assert all({"source_book", "chapter", "chapter_title", "chunk_index"} <= c.metadata.keys() for c in chunks)


def test_every_chunk_overlaps_previous(chunks):
    pairs = [(a, b) for a, b in zip(chunks, chunks[1:]) if a.id.rsplit("-", 1)[0] == b.id.rsplit("-", 1)[0]]
    assert pairs and all(b.text[:30] in a.text for a, b in pairs)


def test_sentence_and_paragraph_boundaries():
    text = " ".join(f"Sentence {i} talks about kaizen and jidoka." for i in range(60))
    assert all(p.endswith(".") for p in RecursiveOverlapSplitter(300, 60).split_text(text))
    paras = "\n\n".join(f"Paragraph {i}. " + "Kaizen improves work step by step. " * 6 for i in range(6))
    assert all(p.endswith("step by step.") for p in RecursiveOverlapSplitter(800, 150).split_text(paras)[:-1])


def test_long_sentences_still_overlap():
    text = " ".join("Toyota " + "very " * 60 + f"long sentence {i}." for i in range(6))
    pieces = RecursiveOverlapSplitter(400, 80).split_text(text)
    assert all(len(p) <= 400 for p in pieces) and all(b[:20] in a for a, b in zip(pieces, pieces[1:]))


def test_bad_overlap():
    with pytest.raises(ValueError):
        RecursiveOverlapSplitter(100, 100)


# ---------------------------------------------------------------- Phase 3: embeddings via OpenRouter

def test_embedder_batches_and_orders():
    client = FakeOpenRouter()
    emb = OpenRouterEmbedder(model="nvidia/nemotron-3-embed-1b:free", client=client, batch_size=2)
    vecs = emb.embed_documents(["a", "bb", "ccc"])
    assert vecs == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]          # re-sorted by index
    assert len(client.embed_calls) == 2                          # 3 texts, batch size 2
    assert client.embed_calls[0]["extra_body"] == {"input_type": "search_document"}
    emb.embed_query("q")
    assert client.embed_calls[-1]["extra_body"] == {"input_type": "search_query"}


def test_embedder_drops_input_type_if_rejected():
    client = FakeOpenRouter(reject_input_type=True)
    emb = OpenRouterEmbedder(model="m", client=client)
    assert emb.embed_query("hello") == [5.0, 1.0]
    assert client.embed_calls[-1]["extra_body"] == {}


# ---------------------------------------------------------------- Phases 4-5: retrieval & generation

def test_retrieval_quality(rag):
    metrics = evaluate(rag.embedder, rag.store, CASES, k=4)
    assert metrics["hit@k"] >= 0.8, metrics


def test_book_filter(rag):
    results = rag.retrieve("What is kaizen?", book="Toyota Corporate History")
    assert results and all(r.metadata["source_book"] == "Toyota Corporate History" for r in results)


def test_same_file_twice_is_not_duplicated(chunks, tmp_path):
    lib = make_library(tmp_path, TfidfEmbedder([c.embedding_text for c in chunks]))
    add_fixture_books(lib)
    again = add_fixture_books(lib)
    assert all(b.get("duplicate") for b in again)
    assert lib.store.count() == len(chunks) and len(lib.list()) == 4


def test_answer_uses_grounded_prompt(rag):
    answer, model, results = rag.ask("What is Just-In-Time manufacturing?")
    call = rag.client.chat_calls[-1]
    prompt = call["messages"][0]["content"]
    assert model == "model-a:free" and call["messages"][0]["role"] == "user"
    assert "If the answer isn't in the context, say \"I don't know\"" in prompt
    assert [int(i) for i in re.findall(r'<passage id="(\d+)"', prompt)] == [1, 2, 3, 4]
    assert prompt.endswith("Question: What is Just-In-Time manufacturing?")
    assert answer.endswith("[1].") and len(results) == 4


def test_falls_back_to_next_free_model(rag):
    client = FakeOpenRouter(fail_models={"model-a:free"})
    rag = ToyotaRAG(rag.embedder, rag.store, client=client, models=["model-a:free", "model-b:free"])
    _, model, _ = rag.ask("What is heijunka?")
    assert model == "model-b:free"


def test_citation_format(rag):
    q = "Why is the company called Toyota instead of Toyoda?"
    assert 'source="Toyota Corporate History (Ch. 1: From Looms to Automobiles (1867-1937))">' in \
        build_prompt(q, rag.retrieve(q))


# ---------------------------------------------------------------- Phase 1a: downloading real sources

def test_wikipedia_text_becomes_chapters():
    from download_books import wiki_to_chapters
    raw = ("Toyota Production System is a system.\n\n== History ==\nOhno developed it.\n"
           "=== Origins ===\nLooms.\n\n== See also ==\nLean\n\n== Concepts ==\nJidoka and JIT.")
    out = wiki_to_chapters(raw)
    assert out.startswith("Chapter 1: Introduction\nToyota Production System is a system.")
    assert "Chapter 2: History" in out and "Chapter 3: Concepts" in out
    assert "\nOrigins\n" in out and "See also" not in out and "Lean" not in out


def test_html_page_becomes_chapters():
    pytest.importorskip("bs4")
    from download_books import html_to_chapters
    html = b"""<html><body><nav><a>Home</a><a>Cars</a></nav><main>
      <h1>Toyota Production System</h1><p>Short</p>
      <p>TPS is a production system based on the philosophy of eliminating all waste.</p>
      <h2>The Two Pillars of TPS</h2><h3>Jidoka</h3>
      <p>Jidoka means the machine stops immediately when a problem occurs.</p>
      <h2>Our Picks</h2><p>Related article that should not be included at all.</p>
    </main><footer>Copyright footer text that is long enough to pass.</footer></body></html>"""
    out = html_to_chapters(html)
    assert out.split("\n")[0] == "Chapter 1: Toyota Production System"
    assert "Chapter 2: The Two Pillars of TPS" in out and "\nJidoka\n" in out
    assert "Short" not in out and "Home" not in out and "Related article" not in out and "Copyright" not in out


def test_catalog_sets_real_titles_and_urls(tmp_path):
    (tmp_path / "wikipedia_kanban.txt").write_text("Chapter 1: Introduction\nKanban is a scheduling system for lean manufacturing.")
    (tmp_path / "sources.json").write_text(json.dumps({"wikipedia_kanban.txt": {
        "title": "Wikipedia: Kanban", "url": "https://en.wikipedia.org/wiki/Kanban", "license": "CC BY-SA 4.0"}}))
    doc = load_directory(tmp_path, verbose=False)[0]
    assert doc.metadata["source_book"] == "Wikipedia: Kanban"
    assert doc.metadata["source_url"] == "https://en.wikipedia.org/wiki/Kanban"


def test_pdf_without_chapters_is_split_by_page(tmp_path):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    from toyota_rag.vectorstores import SearchResult

    path = tmp_path / "report.pdf"
    c = canvas.Canvas(str(path))
    for n in range(1, 4):
        c.drawString(72, 800, "INTEGRATED REPORT 2023")
        for j in range(8):
            c.drawString(72, 700 - 15 * j, f"Page {n} line {j}: Toyota pursues ever-better cars and a mobility society.")
        c.showPage()
    c.save()
    docs = load_pdf(path)
    assert [(d.metadata["chapter_title"], d.metadata["page_start"]) for d in docs] == [
        ("Page 1", 1), ("Page 2", 2), ("Page 3", 3)]
    assert "INTEGRATED REPORT" not in docs[0].text
    assert SearchResult("x", "t", docs[1].metadata, 0.9).citation() == "Report (p. 2)"


def test_retry_after_failure_only_embeds_missing_chunks(chunks, tmp_path):
    class FlakyEmbedder(TfidfEmbedder):
        calls, fail_on = 0, 2

        def embed_documents(self, texts):
            FlakyEmbedder.calls += 1
            if FlakyEmbedder.calls == self.fail_on:
                raise RuntimeError("429 rate limit")
            return super().embed_documents(texts)

    emb = FlakyEmbedder([c.embedding_text for c in chunks])
    lib = make_library(tmp_path, emb)
    tps = DATA / "toyota_production_system.md"          # 26 chunks = 2 batches of 16
    book = lib.add(tps.name, tps.read_bytes(), wait=True)
    assert book["status"] == "error" and "429" in book["error"] and lib.store.count() == 16
    FlakyEmbedder.fail_on = -1
    lib.retry(book["id"])
    lib.wait_idle()
    book = lib.get(book["id"])
    assert book["status"] == "ready" and lib.store.count() == book["chunks"] == 26
    assert book["requests"] == 1                          # only the missing 10 chunks were embedded


# ---------------------------------------------------------------- new formats: DOCX, Markdown without headings

def test_docx_loader(tmp_path):
    import docx
    from toyota_rag.loaders import load_docx

    d = docx.Document()
    d.core_properties.title = "Lean Notes"
    d.add_paragraph("A short preface about the notes.")
    d.add_heading("Just-in-time", level=1)
    d.add_paragraph("Make only what is needed, when it is needed.")
    d.add_heading("Takt time", level=2)
    d.add_paragraph("Takt time is the pace of customer demand.")
    table = d.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Term", "Meaning"
    table.cell(1, 0).text, table.cell(1, 1).text = "Kanban", "Signal card"
    d.add_paragraph("Chapter 7: Jidoka")
    d.add_paragraph("Stop the line when a problem appears.")
    path = tmp_path / "lean.docx"
    d.save(path)

    docs = load_docx(path)
    assert [(x.metadata["chapter"], x.metadata["chapter_title"]) for x in docs] == [
        (0, "Introduction"), (1, "Just-in-time"), (7, "Jidoka")]
    assert docs[0].metadata["source_book"] == "Lean Notes"
    assert "Takt time\n\nTakt time is the pace" in docs[1].text   # level-2 heading kept as text
    assert "Kanban | Signal card" in docs[1].text                    # table row
    assert docs[2].text == "Stop the line when a problem appears."


def test_markdown_without_headings(tmp_path):
    f = tmp_path / "notes.md"
    f.write_text("Kaizen means continuous improvement.\n\nIt involves everyone.")
    docs = load_directory(tmp_path, verbose=False)
    assert len(docs) == 1 and docs[0].metadata["chapter_title"] == "Introduction"


# ---------------------------------------------------------------- library: validation, delete, restart

def test_upload_validation(tmp_path):
    lib = make_library(tmp_path, TfidfEmbedder(["kanban jidoka kaizen"]), max_mb=0.001)
    for name, data, msg in [("book.exe", b"MZ...", "qo‘llab-quvvatlanmaydi"), ("book.pdf", b"", "bo‘sh"),
                            ("book.pdf", b"hello", "mos emas"), ("book.docx", b"%PDF-1.7", "mos emas"),
                            ("big.md", b"x" * 5000, "juda katta")]:
        with pytest.raises(UploadError, match=msg):
            lib.add(name, data)
    assert lib.list() == []


def test_unreadable_file_becomes_error(tmp_path):
    lib = make_library(tmp_path, TfidfEmbedder(["kanban jidoka kaizen"]))
    book = lib.add("empty.md", b"\n\n   \n", wait=True)
    assert book["status"] == "error" and "matn ajratib olinmadi" in book["error"]


def test_delete_removes_vectors_and_file(chunks, tmp_path):
    lib = make_library(tmp_path, TfidfEmbedder([c.embedding_text for c in chunks]))
    books = add_fixture_books(lib)
    victim = books[0]
    assert lib.delete(victim["id"])
    assert all(r[2]["book_id"] != victim["id"] for r in lib.store.rows.values())
    assert not list((tmp_path / "files").glob(victim["id"] + "*"))
    assert len(lib.list()) == 3 and not lib.delete("nope")


def test_catalog_survives_restart_and_resumes_queued(chunks, tmp_path):
    emb = TfidfEmbedder([c.embedding_text for c in chunks])
    lib = make_library(tmp_path, emb)
    book = lib.add("tw.md", (DATA / "the_toyota_way.md").read_bytes(), wait=True)
    lib._update(book["id"], status="embedding")             # pretend the server died mid-way
    lib2 = make_library(tmp_path, emb, store=lib.store)      # "restart"
    lib2.wait_idle()
    assert lib2.get(book["id"])["status"] == "ready"


def test_search_only_selected_books(rag):
    ids = {b["title"]: b["id"] for b in rag.library.list()}
    only = ids["Toyota Hybrid System and Powertrain Technology"]
    results = rag.retrieve("What is kanban?", book_ids=[only])
    assert results and all(r.metadata["book_id"] == only for r in results)


# ---------------------------------------------------------------- website API (Flask test client)

@pytest.fixture()
def client(chunks, tmp_path):
    from app import create_app
    emb = TfidfEmbedder([c.embedding_text for c in chunks])
    lib = make_library(tmp_path, emb)
    rag = ToyotaRAG(emb, lib.store, client=FakeOpenRouter(), models=["model-a:free"])
    app = create_app(library=lib, rag=rag)
    app.testing = True
    c = app.test_client()
    c.library = lib
    return c


def test_api_full_flow(client):
    import io
    assert client.get("/").status_code == 200
    assert client.post("/api/ask", json={"question": "What is jidoka?"}).status_code == 409   # no books yet

    data = (DATA / "toyota_production_system.md").read_bytes()
    r = client.post("/api/books", data={"file": (io.BytesIO(data), "tps.md"), "title": "TPS"},
                    content_type="multipart/form-data")
    assert r.status_code == 202
    book_id = r.get_json()["books"][0]["id"]
    client.library.wait_idle()

    listed = client.get("/api/books").get_json()["books"]
    assert listed[0]["status"] == "ready" and listed[0]["title"] == "TPS" and "chunk_lengths" not in listed[0]
    detail = client.get(f"/api/books/{book_id}").get_json()
    assert len(detail["chunk_lengths"]) == detail["chunks"] and len(detail["preview"]) == 3
    assert client.get("/api/status").get_json()["books_ready"] == 1

    r = client.post("/api/ask", json={"question": "What is jidoka?", "k": 3})
    body = r.get_json()
    assert r.status_code == 200 and body["model"] == "model-a:free" and len(body["sources"]) == 3
    assert body["sources"][0]["book"] == "TPS" and body["sources"][0]["n"] == 1

    assert client.delete(f"/api/books/{book_id}").status_code == 200
    assert client.get("/api/books").get_json()["books"] == []


def test_api_rejects_bad_input(client):
    import io
    r = client.post("/api/books", data={"file": (io.BytesIO(b"MZ"), "virus.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400 and "qo‘llab-quvvatlanmaydi" in r.get_json()["errors"][0]["error"]
    assert client.post("/api/books", data={}, content_type="multipart/form-data").status_code == 400
    assert client.post("/api/ask", json={"question": "  "}).status_code == 400
    assert client.post("/api/ask", json={"question": "x" * 3000}).status_code == 400
    assert client.get("/api/books/unknown").status_code == 404
    assert client.delete("/api/books/unknown").status_code == 404
