#!/usr/bin/env python3
"""Draw the pictures used in README.md (saved to docs/images/).

  python visualize.py                       # chunk charts - offline, no API key
  python visualize.py --embeddings          # 2-D map of the stored vectors (run ingest.py first)
  python visualize.py --embeddings --question "What is jidoka?"   # + the question and its top-4 chunks
"""

import argparse
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from toyota_rag import config  # noqa: E402
from toyota_rag.chunking import chunk_documents  # noqa: E402
from toyota_rag.loaders import load_directory  # noqa: E402

OUT = config.PROJECT_ROOT / "docs" / "images"
COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2",
          "#db2777", "#65a30d", "#ea580c", "#4f46e5", "#0d9488", "#a16207"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def short(book):
    """Short label for charts: 'Wikipedia: Toyota Production System' -> 'Wiki: Toyota Production System'."""
    book = book.replace("Wikipedia: ", "Wiki: ").replace(" (Toyota official website)", " (toyota.com)")
    return book if len(book) <= 34 else book[:32] + "…"


def chunk_charts():
    docs = load_directory(config.DATA_DIR, verbose=False)
    chunks = chunk_documents(docs, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    books = sorted({c.metadata["source_book"] for c in chunks})

    # 1) chunk length histogram
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.hist([len(c.text) for c in chunks], bins=range(0, config.CHUNK_SIZE + 50, 50),
            color=COLORS[0], edgecolor="white")
    ax.axvline(config.CHUNK_SIZE, color=COLORS[1], ls="--", label=f"CHUNK_SIZE = {config.CHUNK_SIZE}")
    ax.set(title=f"Bo‘lak uzunliklari taqsimoti ({len(chunks)} ta bo‘lak)",
           xlabel="Bo‘lak uzunligi (belgi)", ylabel="Bo‘laklar soni")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "chunk_lengths.png", dpi=150)

    # 2) chunks per book
    counts = Counter(c.metadata["source_book"] for c in chunks)
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(books) + 1.2))
    names = [short(b) for b in books]
    bars = ax.barh(names, [counts[b] for b in books], color=[COLORS[i % len(COLORS)] for i in range(len(books))])
    ax.bar_label(bars, padding=3)
    ax.set(title="Har bir manbadan nechta bo‘lak chiqdi", xlabel="Bo‘laklar soni")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "chunks_per_book.png", dpi=150)

    # 3) overlap illustration: chunk positions inside one chapter
    doc = max(docs, key=lambda d: len(d.text))
    pieces = [c for c in chunks if c.metadata["source_file"] == doc.metadata["source_file"]
              and c.metadata["chapter"] == doc.metadata["chapter"]]
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(pieces) + 1.4))
    pos, prev_end = 0, 0
    for i, c in enumerate(pieces):
        start = doc.text.find(c.text, max(0, pos - config.CHUNK_OVERLAP * 2))
        start = start if start >= 0 else pos
        end = start + len(c.text)
        ax.barh(i, end - start, left=start, color=COLORS[0], alpha=0.85, height=0.6)
        if i and prev_end > start:
            ax.barh(i, prev_end - start, left=start, color=COLORS[3], height=0.6,
                    label="overlap (umumiy qism)" if i == 1 else None)
        ax.text(end + 15, i, f"{len(c.text)} belgi", va="center", fontsize=8)
        pos, prev_end = end, end
    ax.set_yticks(range(len(pieces)), [f"bo‘lak {i + 1}" for i in range(len(pieces))])
    ax.invert_yaxis()
    ax.set(title=f"Overlap: “{doc.metadata['chapter_title']}” bobi qanday bo‘laklandi",
           xlabel="Bob matnidagi belgi pozitsiyasi", xlim=(0, prev_end * 1.15))
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "overlap.png", dpi=150)
    concept_figure()
    print(f"Saved chunk_lengths.png, chunks_per_book.png, overlap.png, embedding_concept.png to {OUT}")


def concept_figure():
    """Simplified sketch (hand-placed points, not real vectors) of how semantic search works."""
    groups = {
        "Ishlab chiqarish (TPS)": (COLORS[0], {"Kanban": (1.0, 4.2), "Just-in-Time": (1.6, 4.8),
                                               "Pull tizimi": (0.6, 4.9), "Takt vaqti": (1.9, 4.1)}),
        "Gibrid texnologiya": (COLORS[2], {"Prius": (4.6, 1.2), "Regenerativ tormoz": (5.3, 1.7),
                                           "Atkinson dvigateli": (4.4, 2.0)}),
        "Kompaniya tarixi": (COLORS[3], {"Sakichi Toyoda": (4.8, 4.6), "1937-yil": (5.4, 4.1)}),
    }
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for label, (color, pts) in groups.items():
        for i, (name, (x, y)) in enumerate(pts.items()):
            ax.scatter(x, y, s=140, color=color, label=label if i == 0 else None)
            ax.annotate(name, (x, y), xytext=(7, 6), textcoords="offset points", fontsize=9)
    q = (1.15, 3.55)
    ax.scatter(*q, marker="*", s=420, color="black", label="Savol vektori")
    ax.annotate("“What is Just-In-Time?”", q, xytext=(8, -16), textcoords="offset points", fontsize=9, weight="bold")
    for target in [(1.0, 4.2), (1.6, 4.8), (1.9, 4.1)]:
        ax.annotate("", xy=target, xytext=q, arrowprops=dict(arrowstyle="->", color="black", lw=1))
    ax.annotate("", xy=(4.4, 2.0), xytext=q, arrowprops=dict(arrowstyle="->", color="#9ca3af", ls="--"))
    ax.text(2.6, 2.55, "uzoq = ma’nosi boshqa", color="#6b7280", fontsize=9, rotation=-20)
    ax.set(title="Embedding g‘oyasi (soddalashtirilgan sxema): ma’nosi yaqin matnlar yaqin joylashadi",
           xlim=(0, 6.6), ylim=(0.5, 5.6), xticks=[], yticks=[])
    ax.title.set_fontsize(10)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "embedding_concept.png", dpi=150)


def embedding_map(question=None):
    from sklearn.decomposition import PCA

    from toyota_rag.embeddings import OpenRouterEmbedder
    from toyota_rag.vectorstores import ChromaStore

    data = ChromaStore().get_all()
    if not len(data["ids"]):
        raise SystemExit("The database is empty. Run `python ingest.py` first.")
    vectors = np.array(data["embeddings"], dtype=float)
    books = [m["source_book"] for m in data["metadatas"]]
    pca = PCA(n_components=2).fit(vectors)
    xy = pca.transform(vectors)

    fig, ax = plt.subplots(figsize=(8, 6))
    for idx, book in enumerate(sorted(set(books))):
        color = COLORS[idx % len(COLORS)]
        mask = np.array([b == book for b in books])
        ax.scatter(xy[mask, 0], xy[mask, 1], s=40, color=color, alpha=0.8, label=short(book))
    title = "Embedding xaritasi: har bir nuqta - bitta bo‘lak (PCA, 2D)"
    if question:
        q = np.array(OpenRouterEmbedder().embed_query(question), dtype=float)
        qxy = pca.transform(q[None])[0]
        sims = vectors @ q / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(q))
        for j in np.argsort(-sims)[:config.TOP_K]:
            ax.plot([qxy[0], xy[j, 0]], [qxy[1], xy[j, 1]], color="black", lw=0.8, alpha=0.6)
        ax.scatter(*qxy, marker="*", s=350, color="black", label="savol")
        title += f"\nSavol: “{question}” va unga eng yaqin {config.TOP_K} bo‘lak"
    ax.set(title=title, xlabel="1-komponent", ylabel="2-komponent")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "embedding_map.png", dpi=150)
    print(f"Saved {OUT / 'embedding_map.png'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embeddings", action="store_true", help="plot the stored vectors")
    p.add_argument("--question", help="also show where this question lands")
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.embeddings:
        embedding_map(args.question)
    else:
        chunk_charts()
