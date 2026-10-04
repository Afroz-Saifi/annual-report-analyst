import { useCallback, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { reportPdfUrl } from '../api'
import type { Citation } from '../api'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

type Props = { citation: Citation | null; figures: string[] }

export function PageViewer({ citation, figures }: Props) {
  const [width, setWidth] = useState(0)
  const [pageCount, setPageCount] = useState<number | null>(null)
  const [view, setView] = useState({ citation, page: citation?.page_number ?? 1 })
  // A newly selected source jumps to its page; Previous and Next then move from there.
  if (view.citation !== citation) setView({ citation, page: citation?.page_number ?? 1 })
  const page = view.page
  const setPage = (next: number) => setView({ citation, page: next })

  const frame = useCallback((element: HTMLDivElement | null) => {
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const onCitedPage = citation !== null && page === citation.page_number
  const highlight = useCallback(
    ({ str }: { str: string }) => highlightFigures(str, onCitedPage ? figures : []),
    [figures, onCitedPage],
  )

  if (!citation) {
    return (
      <section className="viewer viewer-empty">
        <p>Select a source to see the page it came from.</p>
      </section>
    )
  }

  return (
    <section className="viewer">
      <header className="viewer-header">
        <div>
          <p className="viewer-title">
            {citation.company} annual report FY{citation.fiscal_year}
          </p>
          <p className="viewer-meta">
            Page {page}
            {pageCount ? ` of ${pageCount}` : ''}
            {onCitedPage ? ' · cited page' : ''}
          </p>
        </div>
        <div className="viewer-actions">
          <button type="button" onClick={() => setPage(page - 1)} disabled={page <= 1}>
            Previous
          </button>
          <button
            type="button"
            onClick={() => setPage(page + 1)}
            disabled={pageCount !== null && page >= pageCount}
          >
            Next
          </button>
          <a href={citation.source_url} target="_blank" rel="noreferrer">
            Original PDF
          </a>
        </div>
      </header>
      <div className="viewer-frame" ref={frame}>
        <Document
          file={reportPdfUrl(citation.report_id)}
          onLoadSuccess={({ numPages }) => setPageCount(numPages)}
          loading={<p className="notice">Loading the report…</p>}
          error={<p className="notice notice-error">Couldn't load this report's PDF.</p>}
        >
          {width > 0 && (
            <Page
              pageNumber={page}
              width={width}
              customTextRenderer={highlight}
              loading={<p className="notice">Loading page {page}…</p>}
            />
          )}
        </Document>
      </div>
    </section>
  )
}

function highlightFigures(text: string, figures: string[]): string {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  if (figures.length === 0) return escaped
  const pattern = figures.map((figure) => figure.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  return escaped.replace(new RegExp(`(?<![\\d,.])(${pattern})(?![\\d,])`, 'g'), '<mark>$1</mark>')
}
