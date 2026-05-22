import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
)

from ingestion.chunker import CodeChunk

load_dotenv()

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
        print(f"Created collection '{collection}'")
    else:
        print(f"Collection '{collection}' already exists")


def upsert_chunks(
    chunks: list[CodeChunk],
    vectors: list[list[float]],
    collection: str,
    id_offset: int = 0,
) -> None:
    """Upsert chunks + their vectors into Qdrant in batches."""
    client = _get_client()
    points = [
        PointStruct(
            id=id_offset + i,
            vector=vec,
            payload={
                "text": chunk.text,
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language,
                "parent_class": chunk.parent_class,
            },
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]

    for i in range(0, len(points), UPSERT_BATCH):
        batch = points[i : i + UPSERT_BATCH]
        client.upsert(collection_name=collection, points=batch)

    print(f"Upserted {len(points)} chunks into '{collection}'")


def collection_size(collection: str) -> int:
    client = _get_client()
    info = client.get_collection(collection)
    return info.points_count or 0
