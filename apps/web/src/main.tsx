import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import type { FormEvent } from 'react'
import WorkflowHistory from './WorkflowHistory'
import './style.css'

interface AnalysisResponse {
  request_id: string
  provider: string
  model: string
  prompt_version: string
  result: { summary: string; key_points: string[] }
  duration_ms: number
  attempts: number
  usage: { input_tokens: number | null; output_tokens: number | null }
  estimated_cost_usd: number | null
}

const errors: Record<string, string> = {
  invalid_input: 'Enter between 1 and 8,000 characters of text.',
  model_timeout: 'The model took too long. Try again with a shorter text.',
  model_unavailable: 'The model is temporarily unavailable. Please try again later.',
  invalid_model_response: 'The model returned an unexpected format. Please try again.',
  internal_error: 'Something went wrong. Share the request ID with the developer.',
}

function App() {
  const [text, setText] = useState('Our four-person team is preparing for the AI Builder Cup. We want to turn a real problem into a working prototype.')
  const [accessCode, setAccessCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<AnalysisResponse | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessCode ? { Authorization: `Bearer ${accessCode}` } : {}),
        },
        body: JSON.stringify({ text }),
        signal: AbortSignal.timeout(100_000),
      })
      const data = await response.json()
      if (!response.ok) {
        const message = response.status === 401
          ? 'Enter the team access code to continue.'
          : errors[data.error?.code] ?? 'The request could not be completed.'
        const id = data.error?.request_id ?? response.headers.get('X-Request-ID')
        throw new Error(`${message}${id ? ` Request ID: ${id}` : ''}`)
      }
      setResult(data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not connect. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return <main>
    <header><span className="mark">B</span><span>AI BUILDER CUP <span className="muted">/ 2026</span></span></header>
    <section className="intro">
      <p className="eyebrow">TEAM PLAYGROUND</p>
      <h1>A small start.<br />A working foundation.</h1>
      <p>Turn a piece of text into a summary and key points. This shared playground is ready for our next idea.</p>
    </section>
    <div className="workspace">
      <form onSubmit={submit}>
        <label htmlFor="text">Your text</label>
        <textarea id="text" required maxLength={8000} value={text} onChange={event => setText(event.target.value)} />
        <div className="count">{text.length.toLocaleString()} / 8,000</div>
        <label htmlFor="access">Team access code <span className="muted">(for shared deployments)</span></label>
        <input id="access" type="password" autoComplete="off" value={accessCode} onChange={event => setAccessCode(event.target.value)} />
        <button disabled={busy || !text.trim()}>{busy ? 'Analyzing…' : 'Analyze text →'}</button>
        {error && <p role="alert" className="error">{error}</p>}
      </form>
      <section className="result" aria-live="polite" aria-busy={busy}>
        <p className="eyebrow">RESULT</p>
        {result ? <>
          {result.provider === 'mock' && <p className="badge">Demo data · no AI model was called</p>}
          <h2>Summary</h2><p>{result.result.summary}</p>
          <h2>Key points</h2><ul>{result.result.key_points.map((point, index) => <li key={index}>{point}</li>)}</ul>
          <details><summary>Run details</summary><dl>
            <dt>Model</dt><dd>{result.model}</dd>
            <dt>Time</dt><dd>{result.duration_ms} ms</dd>
            <dt>Tokens in / out</dt><dd>{result.usage.input_tokens ?? 'Not reported'} / {result.usage.output_tokens ?? 'Not reported'}</dd>
            <dt>Attempts</dt><dd>{result.attempts}</dd>
            <dt>Estimated cost</dt><dd>{result.estimated_cost_usd === null ? 'Pricing not configured' : `$${result.estimated_cost_usd.toFixed(6)}`}</dd>
            <dt>Request</dt><dd>{result.request_id}</dd>
          </dl></details>
        </> : <p className="placeholder">{busy ? 'Reading your text…' : 'Your summary will appear here.'}</p>}
      </section>
    </div>
    <WorkflowHistory />
    <footer>Built together. One useful idea at a time.</footer>
  </main>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
