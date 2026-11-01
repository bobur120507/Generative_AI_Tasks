#!/usr/bin/env python3
"""Ask questions about Toyota (phase 5).

  python query.py "What is Just-In-Time manufacturing?"
  python query.py "Jidoka nima?"                        # questions in Uzbek work too
  python query.py "What is kanban?" --retrieve-only     # show chunks, no chat model
  python query.py "Who is the CEO?" --book "Toyota Corporate History"
  python query.py                                       # interactive mode
"""

import argparse

from toyota_rag import config
from toyota_rag.embeddings import OpenRouterEmbedder
from toyota_rag.rag import ToyotaRAG
from toyota_rag.vectorstores import ChromaStore


def show_chunks(results):
    for i, r in enumerate(results, start=1):
        print(f"--- Chunk {i} | score {r.score:.3f} | {r.citation()} ---\n{r.text}\n")


def answer(rag, question, args):
    results = rag.retrieve(question, k=args.k, book=args.book)
    if args.retrieve_only or args.show_context:
        show_chunks(results)
    if args.retrieve_only:
        return
    text, model = rag.generate(question, results)
    print(f"Answer ({model}):\n\n{text}\n\nSources:")
    for i, r in enumerate(results, start=1):
        print(f"  [{i}] {r.citation()}  score={r.score:.3f}\n      {r.url()}")


def main(args):
    store = ChromaStore()
    if store.count() == 0:
        raise SystemExit("The database is empty. Run `python ingest.py` or upload a book on the website first.")
    rag = ToyotaRAG(OpenRouterEmbedder(), store)
    if args.question:
        answer(rag, args.question, args)
    else:
        print(f"Toyota RAG - {store.count()} chunks. Press Enter on an empty line to quit.")
        while question := input("\nQuestion> ").strip():
            answer(rag, question, args)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("question", nargs="?", help="leave empty for interactive mode")
    p.add_argument("--k", type=int, default=config.TOP_K, help="how many chunks to retrieve")
    p.add_argument("--book", help="search only this book (exact title)")
    p.add_argument("--retrieve-only", action="store_true", help="print the chunks, skip the chat model")
    p.add_argument("--show-context", action="store_true", help="print the chunks before the answer")
    args = p.parse_args()

    try:
        main(args)
    except config.MissingKeyError as exc:
        raise SystemExit(str(exc))
