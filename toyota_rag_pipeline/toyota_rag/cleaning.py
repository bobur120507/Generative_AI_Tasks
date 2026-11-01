"""Phase 1b - text cleaning: page numbers, running headers/footers, broken
hyphenation, ligatures and other extraction artefacts."""

import re
import unicodedata
from collections import Counter

_INVISIBLE = re.compile("[­​‌‍⁠﻿�]")  # soft hyphen, zero-width, BOM, �
_PAGE_NUMBER = [
    re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.I),  # "12", "Page 12", "12 of 300"
    re.compile(r"^\s*[-–—]\s*\d{1,4}\s*[-–—]\s*$"),     # "- 12 -"
    re.compile(r"^\s*(?=[ivx])x{0,3}(ix|iv|v?i{0,3})\s*$"),                # "iv", "xii" (front matter)
]


def is_page_number(line: str) -> bool:
    return any(p.match(line) for p in _PAGE_NUMBER)


def normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)          # "ﬁ" -> "fi", full-width -> ASCII
    text = _INVISIBLE.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")


def remove_headers_footers(pages: list[str], edge_lines: int = 2) -> list[str]:
    """Delete lines that repeat at the top or bottom of at least half the pages
    (book title, chapter running head, "Page 12"...). Digits are ignored when
    comparing, so "Chapter Notes 3" and "Chapter Notes 4" count as the same line."""
    def sig(line):
        return re.sub(r"\d+", "#", line.strip().lower())

    def edge_indexes(lines):
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        return set(idx[:edge_lines] + idx[-edge_lines:])

    split_pages = [p.split("\n") for p in pages]
    counts = Counter()
    for lines in split_pages:
        counts.update({sig(lines[i]) for i in edge_indexes(lines)})

    threshold = max(3, len(pages) // 2)
    repeated = {s for s, n in counts.items() if n >= threshold} if len(pages) >= 3 else set()

    cleaned = []
    for lines in split_pages:
        edges = edge_indexes(lines)
        kept = [ln for i, ln in enumerate(lines) if not (i in edges and sig(ln) in repeated)]
        cleaned.append("\n".join(kept))
    return cleaned


def reflow_paragraphs(text: str) -> str:
    """Join hard-wrapped lines of the same paragraph, keep list items and headings separate."""
    paragraphs = []
    for para in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        merged = []
        for ln in lines:
            new_block = re.match(r"^([-*•]|\d+[.)]|#{1,6}\s)", ln)
            if merged and not new_block and not merged[-1].startswith("#"):
                merged[-1] += " " + ln
            else:
                merged.append(ln)
        if merged:
            paragraphs.append("\n".join(merged))
    return "\n\n".join(paragraphs)


def clean_text(text: str) -> str:
    text = normalize_unicode(text)
    text = "\n".join(ln for ln in text.split("\n") if not is_page_number(ln))
    text = re.sub(r"(\w)-\n\s*([a-z])", r"\1\2", text)          # "manufac-\nturing" -> "manufacturing"
    text = reflow_paragraphs(text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)            # markdown **bold**
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)   # markdown *italic*
    text = re.sub(r"[  ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
