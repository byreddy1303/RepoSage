# RepoSage

**Ask plain-English questions about any GitHub repository and get cited answers that link back to the exact file and line.**

```
"Where is authentication handled?"  →  src/auth/login.py#L42-L88
"What does the payment module depend on?"  →  src/payments/processor.py#L12-L67
```

---

## How It Works

```
  GitHub repo
      │  git clone
      ▼
  ┌─────────────┐    ┌──────────────────┐    ┌──────────────────────┐
  │ File walker │───▶│  tree-sitter     │───▶│  Semantic chunks     │
  │ (skip junk) │    │  AST parser      │    │  + metadata          │
  └─────────────┘    └──────────────────┘    └──────────┬───────────┘
                                                          │  embed (Voyage AI)
                                                          ▼
                                               ┌──────────────────────┐
                                               │   Qdrant vector DB   │
                                               └──────────┬───────────┘
                                                          │
  User question ──▶ embed ──▶ retrieve top-k ──▶ LLM ──▶ cited answer
```

**Ingestion** (once per repo): clone → walk files → parse with tree-sitter → extract function/class/method chunks with metadata → embed → store in Qdrant.

**Query** (every question): embed question → vector search → retrieve top-k chunks → Llama 3.3 70B generates a cited answer.

### The Key Design Decision

Naive RAG splits code every N characters — cutting functions in half and separating them from their context. RepoSage chunks by **syntax tree** (using tree-sitter), so every chunk is a complete function, class, or method with its metadata intact (`file_path`, `start_line`, `end_line`, `language`, `parent_class`). This makes retrieved chunks semantically meaningful.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python 3.12) |
| AST Parsing | tree-sitter (Python, JS, TS, Java, Go) |
| Embeddings | Voyage AI `voyage-code-3` |
| Vector DB | Qdrant Cloud |
| LLM | Groq — Llama 3.3 70B |
| Frontend | React + Tailwind CSS |
| Backend host | GCP Cloud Run |
| Frontend host | Vercel |

---

## Project Structure

```
ingestion/    # Repo cloning, file walking, AST chunking, embedding + Qdrant upsert
retrieval/    # Query embedding, Qdrant search, LLM answer generation
api/          # FastAPI app — /ingest, /query, /health
eval/         # Evaluation harness — recall@k, MRR, faithfulness scoring
frontend/     # React + Tailwind chat UI
```

---

## Running Locally

### 1. Clone and install

```bash
git clone https://github.com/byreddy1303/RepoSage.git
cd RepoSage
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
```

Fill in `.env`:

```
GROQ_API_KEY=...          # free at console.groq.com
VOYAGE_API_KEY=...        # free tier at dash.voyageai.com
QDRANT_URL=...            # free cluster at cloud.qdrant.io
QDRANT_API_KEY=...
GITHUB_TOKEN=...          # GitHub PAT (read-only)
QDRANT_COLLECTION=reposage
```

### 3. Start the backend

```bash
uvicorn api.main:app --reload --port 8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173), paste a GitHub repo URL, and start asking questions.

### CLI (no UI)

```bash
# Ingest a repo
python -c "from ingestion.pipeline import ingest_repo; ingest_repo('https://github.com/pallets/flask')"

# Ask a question
python cli_search.py "how does Flask handle request routing"
```

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/ingest` | Ingest a repository `{"repo_url": "..."}` |
| `POST` | `/query` | Ask a question `{"question": "...", "repo_url": "..."}` |

---

## Running Tests

```bash
pytest ingestion/test_repo_loader.py ingestion/test_chunker.py -v
```

---

## Roadmap

- [ ] Evaluation harness — recall@k, MRR, LLM-as-judge faithfulness scoring
- [ ] Cross-encoder re-ranking
- [ ] Incremental re-indexing (hash-based, only re-embed changed files)
- [ ] Deploy to GCP Cloud Run + Vercel
