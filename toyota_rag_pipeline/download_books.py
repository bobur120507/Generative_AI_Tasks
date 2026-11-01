#!/usr/bin/env python3
"""Phase 1a - download real Toyota sources from the internet into data/books/.

Three kinds of source, three extraction methods:
  * PDF  - Toyota's official Integrated Report      -> saved as .pdf, text extracted later by pypdf
  * HTML - Toyota's official TPS web page            -> text extracted now with BeautifulSoup
  * Wikipedia articles (CC BY-SA 4.0)                -> plain text via the Wikipedia API

Every text source is saved as a .txt file in which each section starts with a
"Chapter N: <title>" line, so the loader can split it into chapters.
data/books/sources.json records title, URL and license of every file (used for citations).

  python download_books.py           # download everything that is not downloaded yet
  python download_books.py --force   # download again
"""

import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

BOOKS_DIR = Path(__file__).resolve().parent / "data" / "books"
USER_AGENT = "ToyotaRAG-coursework/1.0 (educational RAG project; python urllib)"

SOURCES = [
    {"type": "pdf", "file": "toyota_integrated_report_2023.pdf",
     "title": "Toyota Integrated Report 2023",
     "url": "https://global.toyota/pages/global_toyota/ir/library/annual/2023_001_integrated_en.pdf",
     "license": "© Toyota Motor Corporation - downloaded for personal study"},
    {"type": "html", "file": "toyota_official_tps_page.txt",
     "title": "Toyota Production System (Toyota official website)",
     "url": "https://global.toyota/en/company/vision-and-philosophy/production-system/",
     "license": "© Toyota Motor Corporation - downloaded for personal study"},
] + [
    {"type": "wikipedia", "file": f"wikipedia_{re.sub(r'[^a-z0-9]+', '_', t.lower()).strip('_')}.txt",
     "title": f"Wikipedia: {t}", "wiki_title": t,
     "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_")),
     "license": "CC BY-SA 4.0 (Wikipedia contributors)"}
    for t in ["Toyota Production System", "The Toyota Way", "History of Toyota", "Taiichi Ohno",
              "Just-in-time manufacturing", "Kanban", "Autonomation", "Kaizen",
              "Hybrid Synergy Drive", "Toyota Prius"]
]

# Wikipedia sections that are lists of links/references, not content
SKIP_SECTIONS = {"see also", "references", "notes", "further reading", "external links",
                 "bibliography", "citations", "sources", "footnotes", "works cited"}


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


# ------------------------------------------------------------------ Wikipedia

def wikipedia_plaintext(title: str) -> str:
    params = {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
              "format": "json", "formatversion": 2, "titles": title}
    data = json.loads(http_get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)))
    page = data["query"]["pages"][0]
    if "missing" in page:
        raise ValueError(f"Wikipedia article not found: {title}")
    return page["extract"]


def wiki_to_chapters(text: str) -> str:
    """'== History ==' -> 'Chapter 2: History'; drop reference sections; keep '=== Sub ===' as plain lines."""
    out, chapter, skipping = ["Chapter 1: Introduction"], 1, False
    for line in text.split("\n"):
        m = re.match(r"^(=+)\s*(.*?)\s*=+\s*$", line)
        if m:
            level, heading = len(m.group(1)), m.group(2)
            if level == 2:
                skipping = heading.lower() in SKIP_SECTIONS
                if not skipping:
                    chapter += 1
                    out.append(f"\nChapter {chapter}: {heading}")
            elif not skipping:
                out.append(f"\n{heading}")
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out).strip() + "\n"


# ------------------------------------------------------------------ HTML

def html_to_chapters(html: bytes) -> str:
    """Keep headings, paragraphs and list items of the main content; h1/h2 start chapters."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup

    out, chapter, seen = [], 0, set()
    for el in root.find_all(["h1", "h2", "h3", "p", "li"]):
        text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if not text or text in seen:
            continue
        if el.name in ("h1", "h2"):
            if text.lower().startswith("our picks"):   # related-article links at the bottom
                break
            chapter += 1
            out.append(f"\nChapter {chapter}: {text}")
        elif el.name == "h3":
            out.append(f"\n{text}")
        elif len(text) >= 40:                          # skip menu items, buttons, captions
            out.append(text)
        seen.add(text)
    return "\n".join(out).strip() + "\n"


# ------------------------------------------------------------------ main

def download(source: dict, force: bool = False) -> str:
    path = BOOKS_DIR / source["file"]
    if path.exists() and not force:
        return "already downloaded"
    if source["type"] == "pdf":
        data = http_get(source["url"])
        if not data.startswith(b"%PDF"):
            raise ValueError("the server did not return a PDF")
        path.write_bytes(data)
        return f"{len(data) / 1e6:.1f} MB pdf"
    text = wiki_to_chapters(wikipedia_plaintext(source["wiki_title"])) if source["type"] == "wikipedia" \
        else html_to_chapters(http_get(source["url"]))
    if len(text) < 500:
        raise ValueError("too little text extracted")
    path.write_text(text, encoding="utf-8")
    return f"{len(text):,} characters"


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--force", action="store_true", help="download again even if the file exists")
    args = p.parse_args()

    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    catalog = {}
    for src in SOURCES:
        try:
            status = download(src, args.force)
            catalog[src["file"]] = {k: src[k] for k in ("title", "url", "license")}
            print(f"  OK    {src['file']:<48} {status}")
        except Exception as exc:
            print(f"  FAIL  {src['file']:<48} {exc}")
    (BOOKS_DIR / "sources.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(catalog)}/{len(SOURCES)} sources in {BOOKS_DIR}. Next: python ingest.py --dry-run")
