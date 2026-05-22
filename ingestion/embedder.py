import os
import time
from dotenv import load_dotenv
import voyageai

load_dotenv()

_client: voyageai.Client | None = None
VOYAGE_MODEL = "voyage-code-3"
BATCH_SIZE = 128  # Voyage supports up to 128 inputs per request
RETRY_DELAYS = [5, 15, 30, 60]  # seconds between retries on rate limit


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def _embed_batch_with_retry(client: voyageai.Client, batch: list[str], input_type: str) -> list[list[float]]:
    for attempt, delay in enumerate(RETRY_DELAYS + [None]):
        try:
            result = client.embed(batch, model=VOYAGE_MODEL, input_type=input_type)
            return result.embeddings
        except voyageai.error.RateLimitError:
            if delay is None:
                raise
            print(f"  Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{len(RETRY_DELAYS)})...")
            time.sleep(delay)
    raise RuntimeError("Unreachable")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in batches. Returns one vector per text."""
    client = _get_client()
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
        vectors = _embed_batch_with_retry(client, batch, "document")
        all_vectors.extend(vectors)

    return all_vectors


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    client = _get_client()
    vectors = _embed_batch_with_retry(client, [query], "query")
    return vectors[0]
