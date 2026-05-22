import { useState, useRef, useEffect } from 'react'
import { ingestRepo, queryRepo } from './api'
import './index.css'

function CitationLink({ citation, file_path, start_line, repoUrl }) {
  const githubUrl = repoUrl
    ? `${repoUrl}/blob/main/${file_path}#L${start_line}`
    : null

  return githubUrl ? (
    <a
      href={githubUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-block text-xs font-mono bg-violet-100 text-violet-700 hover:bg-violet-200 px-2 py-0.5 rounded border border-violet-300 transition-colors"
    >
      {citation}
    </a>
  ) : (
    <span className="inline-block text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
      {citation}
    </span>
  )
}

function AnswerText({ text }) {
  const parts = text.split(/(```[\s\S]*?```)/g)
  return (
    <div className="text-sm text-gray-800 space-y-2">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const lines = part.slice(3).split('\n')
          const code = lines.slice(1).join('\n').replace(/```$/, '')
          return (
            <pre key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-3 overflow-x-auto text-xs font-mono text-gray-700 whitespace-pre-wrap">
              {code}
            </pre>
          )
        }
        const inlineParts = part.split(/(`[^`]+`)/g)
        return (
          <p key={i} className="leading-relaxed whitespace-pre-wrap">
            {inlineParts.map((s, j) =>
              s.startsWith('`') && s.endsWith('`') ? (
                <code key={j} className="bg-gray-100 text-violet-700 px-1 py-0.5 rounded text-xs font-mono">
                  {s.slice(1, -1)}
                </code>
              ) : s
            )}
          </p>
        )
      })}
    </div>
  )
}

function Message({ msg, repoUrl }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[75%] bg-violet-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
          {msg.content}
        </div>
      </div>
    )
  }

  if (msg.role === 'error') {
    return (
      <div className="flex justify-start mb-3">
        <div className="max-w-[75%] bg-red-50 border border-red-200 text-red-700 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm">
          {msg.content}
        </div>
      </div>
    )
  }

  const { answer, citations } = msg.content
  return (
    <div className="flex justify-start mb-3">
      <div className="max-w-[85%] bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <AnswerText text={answer} />
        {citations && citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs text-gray-400 mb-1.5">Sources</p>
            <div className="flex flex-wrap gap-1.5">
              {citations.map((c, i) => (
                <CitationLink key={i} {...c} repoUrl={repoUrl} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [repoUrl, setRepoUrl] = useState('')
  const [activeRepo, setActiveRepo] = useState(null)
  const [ingesting, setIngesting] = useState(false)
  const [ingestInfo, setIngestInfo] = useState(null)
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, asking])

  async function handleIngest(e) {
    e.preventDefault()
    if (!repoUrl.trim()) return
    const url = repoUrl.trim()
    setIngesting(true)
    setIngestInfo(null)
    setMessages([])
    // Set active repo immediately so chat is usable while indexing runs
    setActiveRepo(url)
    try {
      const result = await ingestRepo(url)
      setIngestInfo(result)
    } catch (err) {
      setIngestInfo({ error: err.message })
    } finally {
      setIngesting(false)
    }
  }

  async function handleQuery(e) {
    e.preventDefault()
    if (!question.trim() || !activeRepo) return
    const q = question.trim()
    setQuestion('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setAsking(true)
    try {
      const result = await queryRepo(q, activeRepo)
      setMessages(prev => [...prev, { role: 'assistant', content: result }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'error', content: err.message }])
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3 sticky top-0 z-10">
        <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center text-white font-bold text-sm select-none">
          R
        </div>
        <span className="font-semibold text-gray-900">RepoSage</span>
        <span className="text-xs text-gray-400 ml-1">code-aware Q&amp;A</span>
      </header>

      <div className="flex-1 flex flex-col max-w-3xl w-full mx-auto px-4 py-6 gap-4">

        {/* Repo input card */}
        <form onSubmit={handleIngest} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
          <label className="block text-xs font-medium text-gray-500 mb-2">
            GitHub Repository URL
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={repoUrl}
              onChange={e => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400 transition"
              disabled={ingesting}
            />
            <button
              type="submit"
              disabled={ingesting || !repoUrl.trim()}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
            >
              {ingesting ? 'Indexing…' : 'Index Repo'}
            </button>
          </div>

          {ingesting && (
            <p className="text-xs text-gray-400 mt-2 animate-pulse">
              Cloning, chunking and embedding — this takes ~30–60s…
            </p>
          )}
          {ingestInfo && !ingestInfo.error && (
            <p className="text-xs text-emerald-600 mt-2">
              ✓ Indexed <strong>{ingestInfo.chunks}</strong> chunks from{' '}
              <strong>{ingestInfo.source_files}</strong> files
            </p>
          )}
          {ingestInfo?.error && (
            <p className="text-xs text-red-500 mt-2">✗ {ingestInfo.error}</p>
          )}
        </form>

        {/* Chat */}
        {activeRepo ? (
          <>
            <div className="flex-1 overflow-y-auto min-h-[320px]">
              {messages.length === 0 && (
                <div className="text-center text-gray-400 text-sm py-16">
                  Ask anything about{' '}
                  <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                    {activeRepo.replace('https://github.com/', '')}
                  </span>
                </div>
              )}
              {messages.map((msg, i) => (
                <Message key={i} msg={msg} repoUrl={activeRepo} />
              ))}
              {asking && (
                <div className="flex justify-start mb-3">
                  <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-400 shadow-sm animate-pulse">
                    Thinking…
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <form
              onSubmit={handleQuery}
              className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm flex gap-2 sticky bottom-4"
            >
              <input
                type="text"
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder={ingesting ? "Indexing… please wait" : "Ask a question about the code…"}
                className="flex-1 text-sm outline-none px-1"
                disabled={asking || ingesting}
                autoFocus
              />
              <button
                type="submit"
                disabled={asking || ingesting || !question.trim()}
                className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
              >
                Ask
              </button>
            </form>
          </>
        ) : (
          !ingesting && (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
              Index a repository above to start asking questions.
            </div>
          )
        )}
      </div>
    </div>
  )
}
