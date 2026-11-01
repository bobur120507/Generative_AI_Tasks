"""Phase 3 - turn text into vectors with a free OpenRouter embedding model
(default: nvidia/nemotron-3-embed-1b:free)."""

import time

from . import config


def call_with_retry(fn, attempts=4):
    """Free models allow ~20 requests/minute. On 429 (rate limit) or 5xx, wait and retry."""
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            network_error = type(exc).__name__ in ("APIConnectionError", "APITimeoutError")
            if attempt == attempts - 1 or not (network_error or status in (429, 500, 502, 503, 504)):
                raise
            wait = 5 * 2 ** attempt
            print(f"    OpenRouter busy ({status or type(exc).__name__}), retrying in {wait}s ...")
            time.sleep(wait)


class OpenRouterEmbedder:
    def __init__(self, model=config.EMBEDDING_MODEL, client=None, batch_size=config.EMBEDDING_BATCH_SIZE):
        self.model = model
        self._client = client          # created on first use, so the website can start without a key
        self.batch_size = batch_size
        self.use_input_type = True  # Nemotron embeds questions and passages slightly differently

    @property
    def client(self):
        if self._client is None:
            self._client = config.get_client()
        return self._client

    def _embed(self, texts, input_type):
        def request(batch):
            extra = {"input_type": input_type} if self.use_input_type else {}
            return self.client.embeddings.create(model=self.model, input=batch,
                                                 encoding_format="float", extra_body=extra)

        vectors = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start:start + self.batch_size])  # many texts per request = fewer requests
            try:
                resp = call_with_retry(lambda: request(batch))
            except Exception as exc:
                if not self.use_input_type or getattr(exc, "status_code", None) != 400:
                    raise
                self.use_input_type = False   # provider doesn't accept input_type -> plain request
                resp = call_with_retry(lambda: request(batch))
            vectors.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
            if len(texts) > self.batch_size:
                print(f"    embedded {len(vectors)}/{len(texts)}")
        return vectors

    def embed_documents(self, texts):
        return self._embed(texts, "search_document")

    def embed_queries(self, texts):
        return self._embed(texts, "search_query")

    def embed_query(self, text):
        return self.embed_queries([text])[0]
