import { createSseParser } from './sse'

export type ReportSummary = {
  id: number
  company: string
  ticker: string
  fiscal_year: number
  page_count: number
  has_pdf: boolean
}

export type Citation = {
  source: number
  report_id: number
  company: string
  fiscal_year: number
  page_number: number
  kind: string
  source_url: string
  excerpt: string
}

export type AgentStep = { step: string; detail: string }

export type AskResponse = {
  answer: string
  citations: Citation[]
  verified: boolean | null
  unverified_figures: string[]
  steps: AgentStep[]
}

export type StreamHandlers = {
  onStep: (step: AgentStep) => void
  onAnswer: (answer: AskResponse) => void
  onError: (detail: string) => void
}

export async function fetchReports(): Promise<ReportSummary[]> {
  const response = await fetch('/api/reports')
  if (!response.ok) throw new Error(`Couldn't load the reports (${response.status}).`)
  return response.json()
}

export function reportPdfUrl(reportId: number): string {
  return `/api/reports/${reportId}/pdf`
}

/** Asks a question and reports each agent step as it arrives, then the answer. */
export async function askStream(question: string, handlers: StreamHandlers): Promise<void> {
  const response = await fetch('/api/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!response.ok || !response.body) {
    handlers.onError(await errorDetail(response))
    return
  }

  let finished = false
  const parser = createSseParser(({ event, data }) => {
    const payload = JSON.parse(data)
    if (event === 'step') handlers.onStep(payload)
    else if (event === 'answer') {
      finished = true
      handlers.onAnswer(payload)
    } else if (event === 'error') {
      finished = true
      handlers.onError(payload.detail)
    }
  })
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    parser.push(value)
  }
  if (!finished) handlers.onError('The connection closed before an answer arrived.')
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // Not a JSON error body; fall through to the status line.
  }
  return `The request failed (${response.status}).`
}
