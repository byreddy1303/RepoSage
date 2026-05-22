const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function ingestRepo(repoUrl) {
  const res = await fetch(`${BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Ingestion failed')
  }
  return res.json()
}

export async function queryRepo(question, repoUrl, topK = 5) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, repo_url: repoUrl, top_k: topK }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Query failed')
  }
  return res.json()
}
