import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './workflow-history.css'

interface WorkflowRun {
  id: string
  scenario: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  outcome: 'accepted' | 'needs_revision' | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  provider: string
  model: string
  prompt_version: string
  attempts: number
  input_tokens: number | null
  output_tokens: number | null
  error_code: string | null
  reason_codes: string[]
}

interface NodeRecord {
  node: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  attempts: number
  input_tokens: number | null
  output_tokens: number | null
  error_code: string | null
}

interface RunDetail extends WorkflowRun { nodes: NodeRecord[] }

const SAMPLE_TEXT = '## 일정\n팀 회의는 금요일 오후 3시에 진행한다.\n## 준비\n발표 자료는 목요일까지 준비한다.\n## 담당자\n발표 담당자는 아직 정하지 않았다.'
const REQUEST_TIMEOUT_MS = 100_000
const RUN_LIMIT = 20
const SCENARIOS = [
  { value: 'normal', label: 'Normal workflow', expected: 'All steps complete with the sample document.' },
  { value: 'timeout', label: 'Model timeout', expected: 'Two calls time out after 1 second each. Extraction fails; join and route are skipped.' },
  { value: 'invalid_json', label: 'Invalid model JSON', expected: 'Invalid JSON fails immediately without a retry. Join and route are skipped.' },
  { value: 'branch_failure', label: 'Parallel branch failure', expected: 'Document inspection fails while extraction is waiting. Extraction is cancelled; join and route are skipped.' },
  { value: 'transient_error', label: 'Transient error then recovery', expected: 'The first connection fails. The second attempt succeeds and the workflow completes.' },
]

class ApiError extends Error {
  constructor(message: string, readonly requestId?: string) { super(message) }
}

async function requestJson<T>(path: string, signal: AbortSignal, body?: object): Promise<T> {
  const response = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
    signal: AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
  })
  const data = await response.json()
  if (!response.ok) {
    throw new ApiError(
      `${data.error?.code ?? 'Request failed'} (HTTP ${response.status})`,
      data.error?.request_id ?? response.headers.get('X-Request-ID') ?? undefined,
    )
  }
  return data as T
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Request failed. Please try again.'
}

function time(value: string | null): string {
  return value ? new Date(value).toLocaleString() : '—'
}

function status(value: string): string {
  return value === 'running' ? 'Running / unfinished' : value.replaceAll('_', ' ')
}

export default function WorkflowHistory() {
  const [enabled, setEnabled] = useState(false)
  const [capabilityError, setCapabilityError] = useState('')
  const [retry, setRetry] = useState(0)
  const [runs, setRuns] = useState<WorkflowRun[]>([])
  const [listBusy, setListBusy] = useState(false)
  const [listError, setListError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [detailBusy, setDetailBusy] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [text, setText] = useState(SAMPLE_TEXT)
  const [scenario, setScenario] = useState('normal')
  const [runBusy, setRunBusy] = useState(false)
  const [runError, setRunError] = useState('')
  const listRequest = useRef<AbortController | null>(null)
  const detailRequest = useRef<AbortController | null>(null)
  const runRequest = useRef<AbortController | null>(null)

  const loadRuns = useCallback(async () => {
    listRequest.current?.abort()
    const controller = new AbortController()
    listRequest.current = controller
    setListBusy(true)
    setListError('')
    try {
      const data = await requestJson<WorkflowRun[]>(`/api/lab/runs?limit=${RUN_LIMIT}`, controller.signal)
      if (!controller.signal.aborted) setRuns(data)
    } catch (error) {
      if (!controller.signal.aborted) setListError(message(error))
    } finally {
      if (!controller.signal.aborted) setListBusy(false)
    }
  }, [])

  const selectRun = useCallback(async (id: string) => {
    detailRequest.current?.abort()
    const controller = new AbortController()
    detailRequest.current = controller
    setSelectedId(id)
    setDetail(null)
    setDetailBusy(true)
    setDetailError('')
    try {
      const data = await requestJson<RunDetail>(`/api/lab/runs/${id}`, controller.signal)
      if (!controller.signal.aborted) setDetail(data)
    } catch (error) {
      if (!controller.signal.aborted) setDetailError(message(error))
    } finally {
      if (!controller.signal.aborted) setDetailBusy(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setCapabilityError('')
    void requestJson<{ workflow_history: boolean }>('/api/capabilities', controller.signal)
      .then(async capabilities => {
        if (controller.signal.aborted) return
        setEnabled(capabilities.workflow_history)
        if (capabilities.workflow_history) await loadRuns()
      })
      .catch(error => { if (!controller.signal.aborted) setCapabilityError(message(error)) })
    return () => {
      controller.abort()
      listRequest.current?.abort()
      detailRequest.current?.abort()
      runRequest.current?.abort()
    }
  }, [loadRuns, retry])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (runBusy || !text.trim()) return
    const controller = new AbortController()
    runRequest.current = controller
    setRunBusy(true)
    setRunError('')
    try {
      const result = await requestJson<{ analysis: { request_id: string } }>(
        '/api/lab/workflow', controller.signal, { text, scenario },
      )
      if (!controller.signal.aborted) await Promise.all([loadRuns(), selectRun(result.analysis.request_id)])
    } catch (error) {
      if (!controller.signal.aborted) {
        setRunError(message(error))
        await Promise.all([
          loadRuns(),
          error instanceof ApiError && error.requestId ? selectRun(error.requestId) : Promise.resolve(),
        ])
      }
    } finally {
      if (!controller.signal.aborted) setRunBusy(false)
    }
  }

  if (capabilityError) return <section className="workflow-history" aria-label="Workflow history">
    <p role="alert" className="error">Workflow history unavailable: {capabilityError}</p>
    <button onClick={() => setRetry(value => value + 1)}>Retry workflow history</button>
  </section>
  if (!enabled) return null

  return <section className="workflow-history" aria-labelledby="workflow-heading">
    <div className="history-heading">
      <div><p className="eyebrow">LOCAL LEARNING LAB</p><h2 id="workflow-heading">Workflow history</h2></div>
      <button disabled={listBusy || detailBusy} onClick={() => void Promise.all([
        loadRuns(), selectedId ? selectRun(selectedId) : Promise.resolve(),
      ])}>Refresh history</button>
    </div>
    <p>Run a mock workflow and inspect its steps. History stores metadata only, without your input or generated text.</p>
    <form className="workflow-form" onSubmit={submit}>
      <label htmlFor="workflow-scenario">Practice scenario</label>
      <select id="workflow-scenario" value={scenario} onChange={event => setScenario(event.target.value)} disabled={runBusy} aria-describedby="scenario-expectation">
        {SCENARIOS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <p id="scenario-expectation" className="history-note">Expected with valid input: {SCENARIOS.find(option => option.value === scenario)?.expected} These simulations only use Mock.</p>
      <label htmlFor="workflow-text">Workflow document</label>
      <textarea id="workflow-text" value={text} onChange={event => setText(event.target.value)} required maxLength={8000} disabled={runBusy} />
      <p className="history-note">Required sections: ## 일정 and ## 준비, each with content. Accepted means these rules passed, not factual accuracy.</p>
      <button disabled={runBusy || !text.trim()}>{runBusy ? 'Running workflow…' : 'Run workflow'}</button>
      {runError && <p role="alert" className="error">{runError}</p>}
    </form>
    <div className="history-grid">
      <aside aria-label="Recent workflow runs" aria-busy={listBusy}>
        <h3>Latest {RUN_LIMIT} runs</h3>
        {listError && <p role="alert" className="error">{listError}</p>}
        {listBusy && <p role="status">Loading runs…</p>}
        {!listBusy && !listError && runs.length === 0 && <p>No runs yet. Start with the sample above.</p>}
        <ul className="run-list">{runs.map(run => <li key={run.id}>
          <button aria-label={`View run ${run.id}`} aria-pressed={selectedId === run.id} onClick={() => void selectRun(run.id)}>
            <span className="run-status" data-status={run.status}>{status(run.status)}</span>
            <span>{status(run.scenario)}</span>
            <span>{run.outcome ? status(run.outcome) : run.error_code ?? 'Awaiting completion'}</span>
            <time dateTime={run.started_at}>{time(run.started_at)}</time>
            <code>{run.id}</code>
          </button>
        </li>)}</ul>
      </aside>
      <section className="run-detail" aria-label="Workflow run details" aria-busy={detailBusy}>
        <h3>Workflow run details</h3>
        {detailError && <p role="alert" className="error">{detailError}</p>}
        {detailBusy && <p role="status">Loading run…</p>}
        {!detailBusy && !detailError && !detail && <p>Choose a run to inspect its nodes.</p>}
        {detail && <>
          <dl>
            <dt>Run ID</dt><dd><code>{detail.id}</code></dd>
            <dt>Scenario</dt><dd>{status(detail.scenario)}</dd>
            <dt>Status</dt><dd data-status={detail.status}>{status(detail.status)}</dd>
            <dt>Outcome</dt><dd>{detail.outcome ? status(detail.outcome) : '—'}</dd>
            <dt>Reason</dt><dd>{detail.error_code ?? (detail.reason_codes.join(', ') || 'None')}</dd>
            <dt>Started</dt><dd>{time(detail.started_at)}</dd>
            <dt>Finished</dt><dd>{time(detail.finished_at)}</dd>
            <dt>Duration</dt><dd>{detail.duration_ms === null ? '—' : `${detail.duration_ms} ms`}</dd>
            <dt>Model</dt><dd>{detail.provider} / {detail.model}</dd>
            <dt>Prompt</dt><dd>{detail.prompt_version}</dd>
            <dt>Attempts</dt><dd>{detail.attempts}</dd>
            <dt>Reported tokens</dt><dd>{detail.input_tokens ?? 'Not reported'} in / {detail.output_tokens ?? 'Not reported'} out</dd>
          </dl>
          {detail.status === 'running' && <p className="history-note">Node snapshots are saved when the run finishes. A stopped API can leave a run unfinished; refreshing does not resume it.</p>}
          <div className="node-table-scroll" role="region" aria-label="Node execution details" tabIndex={0}>
            <table className="node-table">
              <thead><tr>{['Node', 'Status', 'Started', 'Finished', 'Duration', 'Attempts', 'Tokens in / out', 'Error'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
              <tbody>{detail.nodes.map(node => <tr key={node.node}>
                <th scope="row">{node.node}</th><td data-status={node.status}>{status(node.status)}</td>
                <td>{time(node.started_at)}</td><td>{time(node.finished_at)}</td>
                <td>{node.duration_ms === null ? '—' : `${node.duration_ms} ms`}</td><td>{node.attempts}</td>
                <td>{node.node === 'extract' ? `${node.input_tokens ?? 'Not reported'} / ${node.output_tokens ?? 'Not reported'}` : '—'}</td>
                <td>{node.error_code ?? '—'}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <p className="history-note">Scroll the table horizontally for more columns. Node order is the workflow layout; timestamps show execution timing. Tokens cover reported usage and may omit failed provider calls.</p>
        </>}
      </section>
    </div>
  </section>
}
