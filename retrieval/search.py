import os
from dataclasses import dataclass
import config  # noqa: F401  -- loads .env
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint, Filter, FieldCondition, MatchValue

from ingestion.embedder import embed_query


DEFAULT_SCORE_THRESHOLD = 0.35
_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
        )
    return _client


@dataclass
class SearchResult:
    text: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    parent_class: str
    score: float
    repo_url: str

    @property
    def citation(self) -> str:
        return f"{self.file_path}#L{self.start_line}-{self.end_line}"


def search(
    query: str,
    repo_url: str | None = None,
    collection: str | None = None,
    top_k: int = 5,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> list[SearchResult]:
    """Embed query and retrieve top-k matching chunks.

    Pass repo_url to scope results to a single ingested repository.
    """
    collection = collection or os.environ.get("QDRANT_COLLECTION", "reposage")
    client = _get_client()

    query_vector = embed_query(query)

    query_filter = None
    if repo_url:
        query_filter = Filter(
            must=[FieldCondition(key="repo_url", match=MatchValue(value=repo_url))]
        )

    hits: list[ScoredPoint] = client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=top_k,
        score_threshold=score_threshold,
        with_payload=True,
    )

    return [
        SearchResult(
            text=hit.payload["text"],
            file_path=hit.payload["file_path"],
            start_line=hit.payload["start_line"],
            end_line=hit.payload["end_line"],
            language=hit.payload["language"],
            parent_class=hit.payload.get("parent_class", ""),
            score=hit.score,
            repo_url=hit.payload.get("repo_url", ""),
        )
        for hit in hits
    ]
