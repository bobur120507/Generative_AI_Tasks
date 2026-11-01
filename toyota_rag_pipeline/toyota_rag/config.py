"""All settings in one place. Override any of them in the .env file."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# OpenRouter (one free API key for both embeddings and chat)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Phase 1 - data
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data" / "books"))  # filled by download_books.py

# Uploaded books (website + ingest.py)
LIBRARY_DIR = Path(os.getenv("LIBRARY_DIR", PROJECT_ROOT / "data" / "library"))
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", 30))

# Phase 2 - chunking (characters)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))

# Phase 3 - embeddings (free model on OpenRouter)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b:free")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", 64))  # texts per request

# Phase 4 - vector database
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", PROJECT_ROOT / "chroma_toyota_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "toyota_books_collection")

# Phase 5 - retrieval + generation (free chat models, tried in this order)
TOP_K = int(os.getenv("TOP_K", 4))
CHAT_MODELS = [m.strip() for m in os.getenv(
    "CHAT_MODELS",
    "google/gemma-4-31b-it:free,thinkingmachines/inkling-small:free,google/gemma-4-26b-a4b-it:free",
).split(",") if m.strip()]
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 1024))


class MissingKeyError(RuntimeError):
    pass


def get_client():
    """OpenRouter speaks the OpenAI API, so the official `openai` package works as-is."""
    if not OPENROUTER_API_KEY:
        raise MissingKeyError("OPENROUTER_API_KEY is missing. Create a free key at https://openrouter.ai/keys "
                              "and put it in the .env file.")
    from openai import OpenAI
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY, max_retries=0)
