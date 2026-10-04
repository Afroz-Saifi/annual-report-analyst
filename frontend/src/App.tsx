import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { askStream, fetchReports } from './api'
import type { AskResponse, Citation, ReportSummary } from './api'
import { figuresToHighlight } from './answer'
import { Message } from './components/Message'
import type { Exchange } from './components/Message'
import { PageViewer } from './components/PageViewer'
import { ReportList } from './components/ReportList'

const EXAMPLES = [
  'What was consolidated revenue from operations in fiscal 2026?',
  'What dividend per share was recommended for fiscal 2026?',
  'How many employees did Infosys have at the end of the year?',
]

export default function App() {
  const [reports, setReports] = useState<ReportSummary[] | null>(null)
  const [reportsError, setReportsError] = useState<string | null>(null)
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<{ citation: Citation; figures: string[] } | null>(null)
  const nextId = useRef(1)
  const thread = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchReports()
      .then(setReports)
      .catch((error: Error) => setReportsError(error.message))
  }, [])

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight, behavior: 'smooth' })
  }, [exchanges])

  function update(id: number, change: (exchange: Exchange) => Exchange) {
    setExchanges((all) => all.map((exchange) => (exchange.id === id ? change(exchange) : exchange)))
  }

  function select(citation: Citation, answer: AskResponse) {
    setSelected({ citation, figures: figuresToHighlight(answer.answer) })
  }

  async function ask(text: string) {
    const asked = text.trim()
    if (asked.length < 3 || busy) return
    const id = nextId.current++
    setExchanges((all) => [...all, { id, question: asked, steps: [], answer: null, error: null }])
    setQuestion('')
    setBusy(true)
    try {
      await askStream(asked, {
        onStep: (step) => update(id, (e) => ({ ...e, steps: [...e.steps, step] })),
        onAnswer: (answer) => {
          update(id, (e) => ({ ...e, answer }))
          if (answer.citations.length > 0) select(answer.citations[0], answer)
        },
        onError: (error) => update(id, (e) => ({ ...e, error })),
      })
    } catch {
      update(id, (e) => ({ ...e, error: "Couldn't reach the server. Check that the API is running." }))
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void ask(question)
  }

  return (
    <div className="layout">
      <ReportList reports={reports} error={reportsError} />

      <main className="chat">
        <div className="thread" ref={thread}>
          {exchanges.length === 0 && (
            <div className="welcome">
              <h2>Ask about the annual reports</h2>
              <p>Every answer cites its page, and every figure is checked against that page.</p>
              <div className="examples">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" onClick={() => void ask(example)} disabled={busy}>
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}
          {exchanges.map((exchange) => (
            <Message
              key={exchange.id}
              exchange={exchange}
              activeCitation={selected?.citation ?? null}
              onSelectCitation={select}
            />
          ))}
        </div>

        <form className="composer" onSubmit={submit}>
          <label className="visually-hidden" htmlFor="question">
            Your question
          </label>
          <input
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What was total equity as at March 31, 2026?"
            maxLength={500}
            autoComplete="off"
          />
          <button type="submit" className="send" disabled={busy || question.trim().length < 3}>
            {busy ? 'Working…' : 'Ask'}
          </button>
        </form>
      </main>

      <PageViewer citation={selected?.citation ?? null} figures={selected?.figures ?? []} />
    </div>
  )
}
