import asyncio
import config  # noqa: F401 — loads .env with override
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from ingestion.pipeline import ingest_repo
from retrieval.search import search
from retrieval.answerer import answer

app = FastAPI(title="RepoSage", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened at deploy time to the Vercel domain
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── request / response models ──────────────────────────────────────────────

class IngestRequest(BaseModel):
    repo_url: str


class IngestResponse(BaseModel):
    repo_url: str
    source_files: int
    chunks: int
    collection: str
    total_points: int


class QueryRequest(BaseModel):
    question: str
    repo_url: str
    top_k: int = 5


class CitationOut(BaseModel):
    citation: str
    file_path: str
    start_line: int
    end_line: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    model: str


# ── endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    try:
        result = await asyncio.to_thread(ingest_repo, req.repo_url)
        return IngestResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        results = await asyncio.to_thread(
            search, req.question, req.repo_url, None, req.top_k
        )
        out = await asyncio.to_thread(answer, req.question, results)
        return QueryResponse(**out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
