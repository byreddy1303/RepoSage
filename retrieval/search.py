import os
from dataclasses import dataclass
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint

from ingestion.embedder import embed_query

load_dotenv()

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

    @property
    def citation(self) -> str:
        return f"{self.file_path}#L{self.start_line}-{self.end_line}"


def search(query: str, collection: str | None = None, top_k: int = 5) -> list[SearchResult]:
    """Embed query and retrieve top-k matching chunks from Qdrant."""
    collection = collection or os.environ.get("QDRANT_COLLECTION", "reposage")
    client = _get_client()

    query_vector = embed_query(query)
    hits: list[ScoredPoint] = client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=top_k,
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
        )
        for hit in hits
    ]
