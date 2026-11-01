"""Book RAG pipeline (Toyota example) - shared by the website (app.py) and the command line.

library.py                 upload -> validate -> process in a background worker (phases 1-4)
Phase 1  loaders.py + cleaning.py  extract text from PDF / DOCX / Markdown / TXT and clean it
Phase 2  chunking.py               recursive chunking with overlap + metadata
Phase 3  embeddings.py             free OpenRouter embedding model (NVIDIA Nemotron Embed)
Phase 4  vectorstores.py           ChromaDB
Phase 5  rag.py                    retrieve top-k chunks + free OpenRouter chat model (Gemma 4)
"""
