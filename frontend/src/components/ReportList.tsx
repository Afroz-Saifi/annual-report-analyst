import type { ReportSummary } from '../api'

type Props = { reports: ReportSummary[] | null; error: string | null }

export function ReportList({ reports, error }: Props) {
  return (
    <aside className="sidebar">
      <h1 className="brand">Annual Report Analyst</h1>
      <h2 className="sidebar-heading">Reports</h2>
      {error && <p className="notice notice-error">{error}</p>}
      {reports?.length === 0 && (
        <p className="notice">
          No reports yet. Add one to <code>data/reports.yaml</code> and run the ingest command.
        </p>
      )}
      <ul className="report-list">
        {reports?.map((report) => (
          <li key={report.id} className="report">
            <span className="report-name">{report.company}</span>
            <span className="report-meta">
              FY{report.fiscal_year} · {report.page_count} pages
            </span>
          </li>
        ))}
      </ul>
      <p className="sidebar-note">Answers come only from these reports. This is not investment advice.</p>
    </aside>
  )
}
