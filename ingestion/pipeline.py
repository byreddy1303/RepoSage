import os
import tempfile
from dotenv import load_dotenv

from ingestion.repo_loader import load_repo, cleanup
from ingestion.chunker import chunk_files
from ingestion.embedder import embed_texts
from ingestion.vector_store import ensure_collection, upsert_chunks, collection_size

load_dotenv()


def ingest_repo(repo_url: str, collection: str | None = None) -> dict:
    """Full ingestion pipeline: clone → chunk → embed → upsert.

    Returns a summary dict with counts.
    """
    collection = collection or os.environ.get("QDRANT_COLLECTION", "reposage")
    ensure_collection(collection)

    clone_dir = tempfile.mkdtemp(prefix="reposage_")
    try:
        print(f"\n[1/4] Cloning {repo_url}")
        _, source_files = load_repo(repo_url, clone_dir)
        print(f"      Found {len(source_files)} source files")

        print("[2/4] Chunking with tree-sitter AST")
        chunks = chunk_files(source_files)
        print(f"      Produced {len(chunks)} chunks")

        print("[3/4] Embedding chunks via Voyage AI")
        texts = [c.text for c in chunks]
        vectors = embed_texts(texts)
        print(f"      Embedded {len(vectors)} vectors (dim={len(vectors[0])})")

        print("[4/4] Upserting into Qdrant")
        upsert_chunks(chunks, vectors, collection)
        size = collection_size(collection)
        print(f"      Collection '{collection}' now has {size} points\n")

        return {
            "repo_url": repo_url,
            "source_files": len(source_files),
            "chunks": len(chunks),
            "collection": collection,
            "total_points": size,
        }
    finally:
        cleanup(clone_dir)
