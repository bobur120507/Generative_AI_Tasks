"""Phase 5 - retrieve the most relevant chunks and let a free chat model answer.
(Phases 1-4 - upload, extract, chunk, embed, store - live in library.py.)"""

from . import config
from .embeddings import call_with_retry

PROMPT_TEMPLATE = """Use the following context from the books to answer the user's question accurately. \
If the answer isn't in the context, say "I don't know".

Rules:
- Use only the numbered passages below, not outside knowledge.
- Cite the passages you used like [1] or [2][3].
- Answer in the same language as the question.

<context>
{context}
</context>

Question: {question}"""


def build_prompt(question, results):
    context = "\n\n".join(f'<passage id="{i}" source="{r.citation()}">\n{r.text}\n</passage>'
                          for i, r in enumerate(results, start=1))
    return PROMPT_TEMPLATE.format(context=context, question=question)


class ToyotaRAG:
    def __init__(self, embedder, store, client=None, models=None):
        self.embedder = embedder
        self.store = store
        self.client = client
        self.models = models or config.CHAT_MODELS

    def retrieve(self, question, k=config.TOP_K, book=None, book_ids=None):
        """Top-k chunks for the question. Optionally only inside one book title or a list of book ids."""
        where = {}
        if book:
            where["source_book"] = book
        if book_ids:
            where["book_id"] = list(book_ids)
        vector = self.embedder.embed_query(question)
        return self.store.query(vector, k=k, where=where or None)

    def generate(self, question, results):
        """Ask the chat models in order; if one is rate-limited or down, try the next."""
        if not results:
            return "I don't know - no relevant passages were found.", None
        client = self.client or config.get_client()
        # Instructions go in the user message: some free providers ignore a system message.
        messages = [{"role": "user", "content": build_prompt(question, results)}]
        last_error = None
        for model in self.models:
            try:
                resp = call_with_retry(lambda: client.chat.completions.create(
                    model=model, messages=messages, max_tokens=config.MAX_TOKENS, temperature=0.2), attempts=2)
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    return text, model
            except Exception as exc:
                last_error = exc
                print(f"  ! {model} failed: {exc.__class__.__name__}; trying next model")
        raise RuntimeError(f"All chat models failed. Last error: {last_error}")

    def ask(self, question, k=config.TOP_K, book=None, book_ids=None):
        results = self.retrieve(question, k, book, book_ids)
        answer, model = self.generate(question, results)
        return answer, model, results
