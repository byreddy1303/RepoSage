# RepoSage

A code-aware Retrieval-Augmented Generation (RAG) system that ingests a GitHub repository, chunks code by AST using tree-sitter, embeds chunks into Qdrant, and answers natural-language questions with file/line citations via an LLM.

## Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python 3.12) |
| Parsing | tree-sitter (AST-based chunking) |
| Embeddings | Voyage AI `voyage-code-3` |
| Vector DB | Qdrant Cloud |
| LLM | Groq `llama-3.3-70b-versatile` |
| Frontend | React + Tailwind |
| Backend host | GCP Cloud Run |
| Frontend host | Vercel |

## Folder Layout

```
ingestion/    # Repo cloning, file walking, tree-sitter chunking, embedding + Qdrant upsert
retrieval/    # Query embedding, Qdrant search, optional cross-encoder re-ranking
api/          # FastAPI app — /ingest, /query, /health endpoints
eval/         # Labeled test set, recall@k, MRR, faithfulness scoring
frontend/     # React + Tailwind chat UI
```

## Key Design Decision

**AST chunking over fixed-size chunking.** tree-sitter parses each source file into a syntax tree; chunks are extracted at the function/class/method level, each carrying metadata (file_path, start_line, end_line, language, parent_class). This preserves code semantics that naive character-split chunking destroys.

Oversized functions (>150 lines) are sub-chunked with overlap. Unparseable files fall back to line-based chunking.

## Conventions

- All secrets come from `.env` — never hard-coded.
- Each module has a corresponding test file (`test_*.py`).
- Every chunk carries: `text`, `file_path`, `start_line`, `end_line`, `language`, `parent_class`.
- Citations in answers use the format `file_path#Lstart-Lend`.
- Batch all embedding API calls — never one request per chunk.

## Environment Variables

```
GROQ_API_KEY=
VOYAGE_API_KEY=
QDRANT_URL=
QDRANT_API_KEY=
GITHUB_TOKEN=
QDRANT_COLLECTION=reposage
```

## Running Locally

```bash
# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```
