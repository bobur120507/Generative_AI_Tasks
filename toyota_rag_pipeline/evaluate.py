#!/usr/bin/env python3
"""Measure retrieval quality on eval/questions.json.

A question counts as a hit when one of the top-k chunks comes from one of the
expected sources and contains the expected phrase.
  hit@k = share of questions with a hit;  MRR = average of 1/rank of the first hit.

All questions are embedded in ONE request, so this uses only 1 of your daily free requests.

  python evaluate.py
  python evaluate.py --k 2 -v
"""

import argparse
import json

from toyota_rag import config
from toyota_rag.embeddings import OpenRouterEmbedder
from toyota_rag.vectorstores import ChromaStore


def evaluate(embedder, store, cases, k=4, verbose=False):
    vectors = embedder.embed_queries([c["question"] for c in cases])
    hits, reciprocal_ranks = 0, 0.0
    for case, vec in zip(cases, vectors):
        results = store.query(vec, k=k)
        books = case["book"] if isinstance(case["book"], list) else [case["book"]]
        rank = next((i for i, r in enumerate(results, start=1)
                     if r.metadata["source_book"] in books and case["expect"].lower() in r.text.lower()), None)
        if rank:
            hits += 1
            reciprocal_ranks += 1 / rank
        if verbose:
            print(f"  {'OK  ' if rank else 'MISS'} rank={rank or '-'}  {case['question']}")
    return {"hit@k": hits / len(cases), "mrr": reciprocal_ranks / len(cases), "n": len(cases)}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--k", type=int, default=config.TOP_K)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    cases = json.loads((config.PROJECT_ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    m = evaluate(OpenRouterEmbedder(), ChromaStore(), cases, args.k, args.verbose)
    print(f"\n{m['n']} questions | hit@{args.k} = {m['hit@k']:.0%} | MRR = {m['mrr']:.3f}")
