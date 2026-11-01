"""Phase 2 - recursive character chunking with overlap.

1. Split the text into small units: paragraphs -> lines -> sentences
   (and, only for very long sentences, clauses -> words -> characters).
   Each unit remembers which separator ended it (its "boundary strength").
2. Pack units into a chunk of at most CHUNK_SIZE characters. When the chunk is
   full, cut it at the strongest boundary (paragraph > line > sentence ...)
   that keeps the chunk at least half full.
3. Start the next chunk with the last ~CHUNK_OVERLAP characters of the previous
   one (whole sentences when possible), so context crossing a cut is not lost.

This is the same separator hierarchy as LangChain's RecursiveCharacterTextSplitter,
but the overlap is guaranteed (LangChain only overlaps pieces shorter than the overlap).
"""

import re
from dataclasses import dataclass, field

from .loaders import Document

SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]
SENTENCE_LEVEL = 4  # always split down to sentences (indices 0..4)


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def embedding_text(self) -> str:
        """What we send to the embedding model: a 'book - chapter' header + the chunk.
        The header helps because a passage rarely names its own topic."""
        return f"{self.metadata['source_book']} - {self.metadata['chapter_title']}\n{self.text}"


class RecursiveOverlapSplitter:
    def __init__(self, chunk_size=800, chunk_overlap=150, min_fill=0.5):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.size, self.overlap, self.min_fill = chunk_size, chunk_overlap, min_fill
        self.max_unit = chunk_size - chunk_overlap   # a unit + the overlap always fits
        self.weakest = len(SEPARATORS)

    def split_text(self, text: str) -> list[str]:
        return self._merge(self._units(text, 0))

    # step 1: text -> [(unit_text, boundary_strength)]
    def _units(self, text, level):
        if level >= len(SEPARATORS) or SEPARATORS[level] == "":
            step = self.max_unit
            return [(text[i:i + step], self.weakest) for i in range(0, len(text), step)]
        sep = SEPARATORS[level]
        if sep not in text:
            return self._units(text, level + 1)
        parts = text.split(sep)
        pieces = [p + sep for p in parts[:-1]] + [parts[-1]]
        units = []
        for piece in filter(None, pieces):
            strength = level if piece.endswith(sep) else self.weakest
            if level < SENTENCE_LEVEL or len(piece) > self.max_unit:
                sub = self._units(piece, level + 1)
                sub[-1] = (sub[-1][0], min(sub[-1][1], strength))
                units.extend(sub)
            else:
                units.append((piece, strength))
        return units

    # step 2: where to cut a full window
    def _cut_index(self, window, n_overlap):
        best, best_key, filled = len(window), None, 0
        for i, (text, strength) in enumerate(window, start=1):
            filled += len(text)
            if i <= n_overlap or filled < self.min_fill * self.size:
                continue
            key = (strength, -i)          # strongest boundary first, then the latest one
            if best_key is None or key <= best_key:
                best, best_key = i, key
        return best

    # step 3: overlap carried into the next chunk
    def _tail(self, emitted):
        tail, total = [], 0
        for text, strength in reversed(emitted):
            if total + len(text) > self.overlap:
                break
            tail.insert(0, (text, strength))
            total += len(text)
        if tail and tail[0][0].strip():
            return tail
        words, kept = emitted[-1][0].split(" "), []   # last sentence too long: take its last words
        while words and len(" ".join([words[-1]] + kept)) <= self.overlap:
            kept.insert(0, words.pop())
        return [(" ".join(kept), self.weakest)] if kept else []

    def _merge(self, units):
        chunks, window, n_overlap, total = [], [], 0, 0
        for unit in units:
            while window and total + len(unit[0]) > self.size and len(window) > n_overlap:
                cut = self._cut_index(window, n_overlap)
                chunks.append("".join(t for t, _ in window[:cut]).strip())
                tail = self._tail(window[:cut])
                window, n_overlap = tail + window[cut:], len(tail)
                total = sum(len(t) for t, _ in window)
            while window and total + len(unit[0]) > self.size:   # overlap alone too big
                total -= len(window.pop(0)[0])
                n_overlap = max(0, n_overlap - 1)
            window.append(unit)
            total += len(unit[0])
        if len(window) > n_overlap:
            chunks.append("".join(t for t, _ in window).strip())
        return [c for c in chunks if c]


def chunk_documents(docs: list[Document], chunk_size=800, chunk_overlap=150) -> list[Chunk]:
    """Chapter Documents -> overlapping Chunks. IDs are stable (file + chapter + position),
    so running ingest again overwrites old vectors instead of duplicating them."""
    splitter = RecursiveOverlapSplitter(chunk_size, chunk_overlap)
    chunks = []
    for doc in docs:
        stem = re.sub(r"[^a-z0-9]+", "_", doc.metadata["source_file"].rsplit(".", 1)[0].lower())
        for i, piece in enumerate(splitter.split_text(doc.text)):
            meta = {**doc.metadata, "chunk_index": i, "char_count": len(piece)}
            chunks.append(Chunk(f"{stem}-ch{doc.metadata['chapter']}-{i:03d}", piece, meta))
    return chunks
