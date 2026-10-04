export type AnswerPart = { type: 'text'; text: string } | { type: 'citation'; source: number }

/** Splits an answer into plain text and its [n] citation markers. */
export function splitAnswer(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = []
  let last = 0
  for (const match of answer.matchAll(/\[(\d+)\]/g)) {
    if (match.index > last) parts.push({ type: 'text', text: answer.slice(last, match.index) })
    parts.push({ type: 'citation', source: Number(match[1]) })
    last = match.index + match[0].length
  }
  if (last < answer.length) parts.push({ type: 'text', text: answer.slice(last) })
  return parts
}

/**
 * The figures in an answer worth highlighting on the cited page. Years and
 * one- or two-digit numbers appear all over a report, so they are left out.
 */
export function figuresToHighlight(answer: string): string[] {
  const withoutMarkers = answer.replace(/\[\d+\]/g, ' ')
  const figures = withoutMarkers.match(/(?<![A-Za-z\d.,])\d[\d,]*(?:\.\d+)?/g) ?? []
  const cleaned = figures.map((figure) => figure.replace(/,$/, ''))
  return [...new Set(cleaned)].filter(
    (figure) => figure.replace(/\D/g, '').length >= 3 && !/^(19|20)\d\d$/.test(figure),
  )
}
