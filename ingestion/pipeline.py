import os
import tempfile
import config  # noqa: F401  -- loads .env

from ingestion.repo_loader import load_repo, cleanup
from ingestion.chunker import chunk_files, CodeChunk
from ingestion.embedder import embed_texts
from ingestion.vector_store import (
    ensure_collection,
    upsert_chunks,
    delete_stale_chunks,
    collection_size,
)

MIN_CHUNK_CHARS = 10


def _filter_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    return [c for c in chunks if len(c.text.strip()) >= MIN_CHUNK_CHARS]


def ingest_repo(repo_url: str, collection: str | None = None) -> dict:
    """Full ingestion pipeline: clone → chunk → embed → upsert → delete stale.

    Atomic swap: new chunks are inserted BEFORE old ones are removed, so
    search always returns results — even during a re-index of the same repo.
    """
    collection = collection or os.environ.get("QDRANT_COLLECTION", "reposage")
    ensure_collection(collection)

    clone_dir = tempfile.mkdtemp(prefix="reposage_")
    try:
        print(f"\n[1/4] Cloning {repo_url}")
        _, source_files = load_repo(repo_url, clone_dir)
        print(f"      Found {len(source_files)} source files")

        if not source_files:
            print("      No supported source files found — skipping.")
            return {"repo_url": repo_url, "source_files": 0, "chunks": 0,
                    "collection": collection, "total_points": collection_size(collection)}

        print("[2/4] Chunking with tree-sitter AST")
        raw_chunks = chunk_files(source_files)
        chunks = _filter_chunks(raw_chunks)
        skipped = len(raw_chunks) - len(chunks)
        print(f"      Produced {len(chunks)} chunks ({skipped} empty skipped)")

        if not chunks:
            print("      No non-empty chunks — skipping.")
            return {"repo_url": repo_url, "source_files": len(source_files), "chunks": 0,
                    "collection": collection, "total_points": collection_size(collection)}

        print("[3/4] Embedding chunks via Voyage AI")
        vectors = embed_texts([c.text for c in chunks])
        print(f"      Embedded {len(vectors)} vectors (dim={len(vectors[0])})")

        print("[4/4] Upserting into Qdrant (atomic swap: insert new → delete stale)")
        current_ids = upsert_chunks(chunks, vectors, collection, repo_url)
        delete_stale_chunks(repo_url, collection, current_ids)
        size = collection_size(collection)
        print(f"      Collection '{collection}' now has {size} total points\n")

        return {
            "repo_url": repo_url,
            "source_files": len(source_files),
            "chunks": len(chunks),
            "collection": collection,
            "total_points": size,
        }
    finally:
        cleanup(clone_dir)
