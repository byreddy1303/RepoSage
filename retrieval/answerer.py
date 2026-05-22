import os
import anthropic
import config  # noqa: F401  -- loads .env

from retrieval.search import SearchResult


MODEL = "claude-haiku-4-5-20251001"
MAX_CONTEXT_CHUNKS = 8
MAX_TOKENS = 1024

_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT = """\
You are RepoSage, a code-understanding assistant. You answer questions about a \
software repository using ONLY the code excerpts provided. Every factual claim \
you make must be supported by the provided excerpts.

Rules:
- Cite sources inline using the format `file_path#Lstart-Lend` (e.g. `src/auth/login.py#L42-L88`).
- If the excerpts do not contain enough information to answer, say so explicitly — do NOT guess or hallucinate.
- Keep answers concise and technical. Use markdown code blocks for any code you quote.
"""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _build_context(results: list[SearchResult]) -> str:
    parts = []
    for r in results[:MAX_CONTEXT_CHUNKS]:
        parts.append(
            f"### {r.citation}\n```{r.language}\n{r.text}\n```"
        )
    return "\n\n".join(parts)


def answer(query: str, results: list[SearchResult]) -> dict:
    """Generate a cited answer from retrieved code chunks.

    Returns:
        {
            "answer": str,
            "citations": [{"citation": str, "file_path": str, "start_line": int, "end_line": int}],
            "model": str,
        }
    """
    if not results:
        return {
            "answer": "No relevant code was found in the repository for that question.",
            "citations": [],
            "model": MODEL,
        }

    context = _build_context(results)
    user_message = f"""Question: {query}

Code excerpts from the repository:

{context}

Answer the question using only the code above. Cite every source you reference."""

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    answer_text = response.content[0].text

    citations = [
        {
            "citation": r.citation,
            "file_path": r.file_path,
            "start_line": r.start_line,
            "end_line": r.end_line,
            "score": r.score,
        }
        for r in results[:MAX_CONTEXT_CHUNKS]
    ]

    return {
        "answer": answer_text,
        "citations": citations,
        "model": MODEL,
    }
