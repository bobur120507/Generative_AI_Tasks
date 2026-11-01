"""Phase 4 - store vectors in ChromaDB and search them by cosine similarity."""

from dataclasses import dataclass

from . import config


@dataclass
class SearchResult:
    id: str
    text: str
    metadata: dict
    score: float  # cosine similarity, 1.0 = identical meaning

    def citation(self) -> str:
        m = self.metadata
        if str(m.get("chapter_title", "")).startswith("Page "):   # page-based PDF
            return f"{m['source_book']} (p. {m['page_start']})"
        ref = f"{m['source_book']} (Ch. {m['chapter']}: {m['chapter_title']}"
        if "page_start" in m:
            ref += f", pp. {m['page_start']}-{m['page_end']}"
        return ref + ")"

    def url(self) -> str:
        return self.metadata.get("source_url", "")


def chroma_where(where):
    """{"book_id": ["a", "b"], "chapter": 3} -> Chroma filter syntax ($in for lists, $and for several keys)."""
    if not where:
        return None
    parts = [{k: {"$in": list(v)} if isinstance(v, (list, tuple, set)) else v} for k, v in where.items()]
    return parts[0] if len(parts) == 1 else {"$and": parts}


def matches(meta, where):
    """Same filter, evaluated in Python (used by MemoryStore)."""
    return not where or all(meta.get(k) in v if isinstance(v, (list, tuple, set)) else meta.get(k) == v
                            for k, v in where.items())


class ChromaStore:
    def __init__(self, path=config.CHROMA_PATH, name=config.COLLECTION_NAME):
        import chromadb

        self.name = name
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self._open()

    def _open(self):
        # embedding_function=None: we always pass our own OpenRouter vectors
        return self.client.get_or_create_collection(
            self.name, embedding_function=None, metadata={"hnsw:space": "cosine"})

    def reset(self):
        try:
            self.client.delete_collection(self.name)
        except Exception:
            pass
        self.collection = self._open()

    def upsert(self, ids, vectors, texts, metadatas):
        self.collection.upsert(ids=list(ids), embeddings=[list(v) for v in vectors],
                               documents=list(texts), metadatas=list(metadatas))

    def query(self, vector, k=4, where=None):
        res = self.collection.query(query_embeddings=[list(vector)], n_results=k, where=chroma_where(where),
                                    include=["documents", "metadatas", "distances"])
        return [SearchResult(i, doc, meta, 1.0 - dist)  # Chroma returns cosine *distance*
                for i, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                              res["metadatas"][0], res["distances"][0])]

    def count(self):
        return self.collection.count()

    def delete(self, where):
        """Remove every chunk matching the filter, e.g. delete({"book_id": "3fa1..."})."""
        self.collection.delete(where=chroma_where(where))

    def existing_texts(self, ids):
        """{id: stored text} for ids already in the collection."""
        got = self.collection.get(ids=list(ids), include=["documents"])
        return dict(zip(got["ids"], got["documents"]))

    def get_all(self):
        """Every stored chunk with its vector (used by visualize.py)."""
        return self.collection.get(include=["embeddings", "metadatas", "documents"])


class MemoryStore:
    """Tiny in-memory store with the same interface - used by the offline tests."""

    def __init__(self):
        self.rows = {}

    def reset(self):
        self.rows = {}

    def upsert(self, ids, vectors, texts, metadatas):
        for i, v, t, m in zip(ids, vectors, texts, metadatas):
            self.rows[i] = (v, t, m)

    def query(self, vector, k=4, where=None):
        import numpy as np

        items = [(i, r) for i, r in self.rows.items() if matches(r[2], where)]
        if not items:
            return []
        mat = np.array([r[0] for _, r in items], dtype=float)
        q = np.array(vector, dtype=float)
        sims = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-12)
        return [SearchResult(items[j][0], items[j][1][1], items[j][1][2], float(sims[j]))
                for j in np.argsort(-sims)[:k]]

    def count(self):
        return len(self.rows)

    def existing_texts(self, ids):
        return {i: self.rows[i][1] for i in ids if i in self.rows}

    def delete(self, where):
        self.rows = {i: r for i, r in self.rows.items() if not matches(r[2], where)}
