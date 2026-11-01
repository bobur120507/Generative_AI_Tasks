#!/usr/bin/env python3
"""The roadmap's quickstart snippet, corrected so it runs.

Fixes vs. the original:
  * `Chroma.from_documents(..., persist_db_dir=...)` -> the argument is `persist_directory`.
  * `langchain_community.vectorstores.Chroma` is deprecated -> `langchain_chroma.Chroma`.
  * Loads every .md/.txt file in data/raw instead of one hard-coded file.
  * Uses a free local embedding model by default; set USE_OPENAI=1 for text-embedding-3-small.

Needs:  pip install langchain-text-splitters langchain-community langchain-chroma langchain-huggingface
        (and langchain-openai if USE_OPENAI=1)
The full pipeline (ingest.py / query.py) does not need LangChain at all.
"""

import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT = Path(__file__).resolve().parent

# 1. Load Toyota book/document data
loader = DirectoryLoader(str(ROOT / "data" / "raw"), glob="**/*.md", loader_cls=TextLoader,
                         loader_kwargs={"encoding": "utf-8"})
docs = loader.load()

# 2. Chunk with overlap
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
chunks = text_splitter.split_documents(docs)
print(f"{len(docs)} files -> {len(chunks)} chunks")

# 3. Embed and store in ChromaDB
if os.environ.get("USE_OPENAI"):
    from langchain_openai import OpenAIEmbeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
else:
    from langchain_huggingface import HuggingFaceEmbeddings
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5",
                                       encode_kwargs={"normalize_embeddings": True})

vector_store = Chroma.from_documents(
    chunks, embeddings,
    collection_name="toyota_langchain_quickstart",
    persist_directory=str(ROOT / "chroma_toyota_langchain_db"),   # <- was persist_db_dir
)

# 4. Set up Retriever
retriever = vector_store.as_retriever(search_kwargs={"k": 4})

# 5. Retrieve relevant chunks for a query
relevant_docs = retriever.invoke("What is Just-In-Time manufacturing?")
for i, doc in enumerate(relevant_docs):
    print(f"--- Chunk {i + 1} ({Path(doc.metadata['source']).name}) ---\n{doc.page_content}\n")
