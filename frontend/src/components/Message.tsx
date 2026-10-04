import type { AgentStep, AskResponse, Citation } from '../api'
import { splitAnswer } from '../answer'

export type Exchange = {
  id: number
  question: string
  steps: AgentStep[]
  answer: AskResponse | null
  error: string | null
}

const STEP_LABELS: Record<string, string> = {
  retrieve: 'Searched the reports',
  answer: 'Read the sources',
  rewrite: 'Tried different searches',
  verify: 'Checked the figures',
}

type Props = {
  exchange: Exchange
  activeCitation: Citation | null
  onSelectCitation: (citation: Citation, answer: AskResponse) => void
}

export function Message({ exchange, activeCitation, onSelectCitation }: Props) {
  const { question, steps, answer, error } = exchange
  const working = !answer && !error

  return (
    <article className="exchange">
      <p className="question">{question}</p>

      <ol className="steps" aria-live="polite">
        {steps.map((step, index) => (
          <li key={index} className="step">
            <span className="step-label">{STEP_LABELS[step.step] ?? step.step}</span>
            <span className="step-detail">{step.detail}</span>
          </li>
        ))}
        {working && <li className="step step-working">Working…</li>}
      </ol>

      {error && <p className="notice notice-error">{error}</p>}

      {answer && (
        <div className="answer">
          <p className="answer-text">
            {splitAnswer(answer.answer).map((part, index) => {
              if (part.type === 'text') return <span key={index}>{part.text}</span>
              const citation = answer.citations.find((c) => c.source === part.source)
              if (!citation) return null
              return (
                <button
                  key={index}
                  type="button"
                  className="citation-chip"
                  aria-pressed={citation === activeCitation}
                  aria-label={`Source ${part.source}: page ${citation.page_number}`}
                  onClick={() => onSelectCitation(citation, answer)}
                >
                  {part.source}
                </button>
              )
            })}
          </p>

          {answer.verified === true && (
            <p className="badge badge-ok">Every figure appears on a cited page</p>
          )}
          {answer.verified === false && (
            <p className="badge badge-warn">
              Not found on the cited pages: {answer.unverified_figures.join(', ')}
            </p>
          )}

          {answer.citations.length > 0 && (
            <ul className="sources">
              {answer.citations.map((citation) => (
                <li key={citation.source}>
                  <button
                    type="button"
                    className="source-link"
                    aria-pressed={citation === activeCitation}
                    onClick={() => onSelectCitation(citation, answer)}
                  >
                    <span className="source-number">{citation.source}</span>
                    {citation.company} FY{citation.fiscal_year} · page {citation.page_number}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </article>
  )
}
