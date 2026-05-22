import os
import uuid
import config  # noqa: F401  -- loads .env
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
    Filter,
    FieldCondition,
    MatchValue,
    HasIdCondition,
)

from ingestion.chunker import CodeChunk

VECTOR_DIM = 1024  # voyage-code-3 output dimension
UPSERT_BATCH = 256

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
        )
    return _client


def chunk_id(repo_url: str, file_path: str, start_line: int) -> str:
    """Deterministic UUID5 from repo + file + line — same chunk always gets the same ID."""
    key = f"{repo_url}::{file_path}::{start_line}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def ensure_collection(collection: str) -> None:
    """Create the Qdrant collection if it doesn't already exist."""
    client = _get_client()
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        client.create_payload_index(collection, "language", PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection, "file_path", PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection, "repo_url", PayloadSchemaType.KEYWORD)
        print(f"Created collection '{collection}'")
    else:
        print(f"Collection '{collection}' already exists")


def upsert_chunks(
    chunks: list[CodeChunk],
    vectors: list[list[float]],
    collection: str,
    repo_url: str,
) -> list[str]:
    """Upsert chunks + vectors into Qdrant. Returns the list of point IDs upserted."""
    client = _get_client()
    ids = [chunk_id(repo_url, c.file_path, c.start_line) for c in chunks]

    points = [
        PointStruct(
            id=point_id,
            vector=vec,
            payload={
                "text": chunk.text,
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language,
                "parent_class": chunk.parent_class,
                "repo_url": repo_url,
            },
        )
        for point_id, chunk, vec in zip(ids, chunks, vectors)
    ]

    for i in range(0, len(points), UPSERT_BATCH):
        client.upsert(collection_name=collection, points=points[i : i + UPSERT_BATCH])

    print(f"Upserted {len(points)} chunks into '{collection}'")
    return ids


def delete_stale_chunks(repo_url: str, collection: str, current_ids: list[str]) -> None:
    """Delete any points for repo_url whose IDs are NOT in current_ids.

    Called AFTER upsert so the collection is never empty during a re-index.
    """
    client = _get_client()
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="repo_url", match=MatchValue(value=repo_url))],
            must_not=[HasIdCondition(has_id=current_ids)],
        ),
    )


def collection_size(collection: str) -> int:
    client = _get_client()
    info = client.get_collection(collection)
    return info.points_count or 0
