"""Phase 1 - load books (PDF, DOCX, Markdown, TXT) and split them into chapters.

Each chapter becomes a Document with metadata:
    source_book, source_file, chapter, chapter_title (+ page_start / page_end for PDF)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .cleaning import clean_text, normalize_unicode, remove_headers_footers

SUPPORTED = {".pdf", ".docx", ".md", ".txt"}
_CHAPTER = re.compile(r"^\s*(?:#\s*)?chapter\s+(\d+)\b[\s:.\-–—]*(.*)$", re.I)


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


def parse_chapter_heading(line: str):
    """'Chapter 3: Jidoka' -> (3, 'Jidoka');  anything else -> None"""
    m = _CHAPTER.match(line.strip())
    if not m:
        return None
    num = int(m.group(1))
    return num, m.group(2).strip() or f"Chapter {num}"


def title_from_filename(path: Path) -> str:
    """toyota_production_system.pdf -> 'Toyota Production System'"""
    return " ".join(w.capitalize() for w in re.split(r"[_\-\s]+", path.stem) if w)


def _make_doc(body, title, path, num, ch_title, **extra):
    meta = {"source_book": title, "source_file": path.name, "chapter": num, "chapter_title": ch_title, **extra}
    return Document(body, meta)


def load_markdown(path: Path) -> list[Document]:
    raw = normalize_unicode(path.read_text(encoding="utf-8"))
    title = title_from_filename(path)
    front = re.match(r"^---\n(.*?)\n---\n", raw, re.S)  # optional front matter with "title: ..."
    if front:
        t = re.search(r"^title:\s*(.+)$", front.group(1), re.M)
        title = t.group(1).strip().strip("\"'") if t else title
        raw = raw[front.end():]

    parts = re.split(r"^#\s+(.+)$", raw, flags=re.M)  # every "# Heading" starts a chapter
    sections = list(zip(parts[1::2], parts[2::2]))
    if parts[0].strip():  # text before the first heading (or a file without any headings)
        sections.insert(0, ("Introduction", parts[0]))
    docs = []
    for i, (heading, body) in enumerate(sections, start=1):
        num, ch_title = parse_chapter_heading(heading) or (i, heading.strip())
        body = re.sub(r"^#{2,6}\s+", "", clean_text(body), flags=re.M)  # keep "## Kanban" as plain text
        if body:
            docs.append(_make_doc(body, title, path, num, ch_title))
    return docs


def _split_chapters(lines_with_pages):
    """Group (line, page) pairs into chapters wherever a 'Chapter N' line appears."""
    chapters = [{"num": 0, "title": "Front matter", "lines": [], "pages": []}]
    for line, page in lines_with_pages:
        heading = parse_chapter_heading(line)
        if heading:
            chapters.append({"num": heading[0], "title": heading[1], "lines": [], "pages": [page]})
        else:
            chapters[-1]["lines"].append(line)
            chapters[-1]["pages"].append(page)
    return chapters


def load_text(path: Path) -> list[Document]:
    raw = normalize_unicode(path.read_text(encoding="utf-8"))
    docs = []
    for ch in _split_chapters((ln, 0) for ln in raw.split("\n")):
        body = clean_text("\n".join(ch["lines"]))
        if body:
            docs.append(_make_doc(body, title_from_filename(path), path, ch["num"], ch["title"]))
    return docs


def load_pdf(path: Path) -> list[Document]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    meta_title = (reader.metadata or {}).get("/Title") if reader.metadata else None
    meta_title = (meta_title or "").strip()
    placeholder = meta_title.lower() in ("", "untitled", "document") or meta_title.lower().startswith("microsoft")
    title = title_from_filename(path) if placeholder or len(meta_title) <= 3 else meta_title

    pages = remove_headers_footers([normalize_unicode(p.extract_text() or "") for p in reader.pages])
    lines = [(ln, n) for n, page in enumerate(pages, start=1) for ln in page.split("\n") + [""]]
    chapters = _split_chapters(lines)

    docs = []
    if len(chapters) > 1:  # the book has "Chapter N" headings
        for ch in chapters:
            body = clean_text("\n".join(ch["lines"]))
            if len(body) > 50:
                docs.append(_make_doc(body, title, path, ch["num"], ch["title"],
                                      page_start=min(ch["pages"]), page_end=max(ch["pages"])))
    else:  # reports, brochures: no chapters -> one Document per page, so citations keep page numbers
        for n, page in enumerate(pages, start=1):
            body = clean_text(page)
            if len(body) > 200:  # skip covers and full-page pictures
                docs.append(_make_doc(body, title, path, n, f"Page {n}", page_start=n, page_end=n))
    return docs


def load_docx(path: Path) -> list[Document]:
    """Word file: 'Title' / 'Heading 1' paragraphs (or 'Chapter N' lines) start chapters,
    lower headings stay as text, tables become 'cell | cell' lines."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(str(path))
    title = (d.core_properties.title or "").strip() or title_from_filename(path)

    chapters = [{"num": 0, "title": "Introduction", "lines": []}]
    for el in d.element.body.iterchildren():           # paragraphs and tables in document order
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            for row in Table(el, d).rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    chapters[-1]["lines"].append(" | ".join(dict.fromkeys(cells)))  # merged cells repeat
            chapters[-1]["lines"].append("")
            continue
        if tag != "p":
            continue
        para = Paragraph(el, d)
        text = para.text.strip()
        style = (para.style.name if para.style is not None else "").lower()
        heading = parse_chapter_heading(text) if text else None
        if text and (style in ("title", "heading 1") or heading):
            num, ch_title = heading or (len(chapters), text)
            chapters.append({"num": num, "title": ch_title, "lines": []})
        else:
            chapters[-1]["lines"].extend([text, ""])  # each Word paragraph is its own paragraph

    docs = []
    for ch in chapters:
        body = clean_text("\n".join(ch["lines"]))
        if body:
            docs.append(_make_doc(body, title, path, ch["num"], ch["title"]))
    return docs


LOADERS = {".pdf": load_pdf, ".docx": load_docx, ".md": load_markdown, ".txt": load_text}


def load_file(path, title: str | None = None, url: str | None = None) -> list[Document]:
    """Load one file of any supported type; optionally override its title / attach a source URL."""
    path = Path(path)
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported file type {path.suffix!r}. Supported: {', '.join(sorted(SUPPORTED))}")
    docs = loader(path)
    for d in docs:
        if title:
            d.metadata["source_book"] = title
        if url:
            d.metadata["source_url"] = url
    return docs


def _read_catalog(directory: Path) -> dict:
    """data/books/sources.json (written by download_books.py): file -> {title, url, license}."""
    f = directory / "sources.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def load_directory(directory, verbose=True) -> list[Document]:
    directory = Path(directory)
    files = sorted(p for p in directory.rglob("*") if p.suffix.lower() in SUPPORTED)
    if not files:
        raise SystemExit(f"No .pdf/.md/.txt files found in {directory}. "
                         "Run `python download_books.py` first.")
    catalog = _read_catalog(directory)
    docs = []
    for f in files:
        info = catalog.get(f.name, {})  # real title and link of the source, for citations
        file_docs = load_file(f, info.get("title"), info.get("url"))
        docs.extend(file_docs)
        if verbose:
            chars = sum(len(d.text) for d in file_docs)
            print(f"  {f.name:<48} {len(file_docs):>3} sections {chars:>8,} chars")
    return docs
