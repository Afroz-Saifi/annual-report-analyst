import { describe, expect, it } from 'vitest'
import { figuresToHighlight, splitAnswer } from './answer'

describe('splitAnswer', () => {
  it('separates text from citation markers', () => {
    expect(splitAnswer('Revenue was ₹1,78,650 crore [3]. EPS was 71.58 [1][2].')).toEqual([
      { type: 'text', text: 'Revenue was ₹1,78,650 crore ' },
      { type: 'citation', source: 3 },
      { type: 'text', text: '. EPS was 71.58 ' },
      { type: 'citation', source: 1 },
      { type: 'citation', source: 2 },
      { type: 'text', text: '.' },
    ])
  })

  it('returns one text part when there are no citations', () => {
    expect(splitAnswer('The sources do not say.')).toEqual([
      { type: 'text', text: 'The sources do not say.' },
    ])
  })

  it('returns nothing for an empty answer', () => {
    expect(splitAnswer('')).toEqual([])
  })
})

describe('figuresToHighlight', () => {
  it('keeps the figures and drops citation markers, years and short numbers', () => {
    const answer = 'In fiscal 2026 revenue was ₹1,78,650 crore, up from 1,62,990, and EPS 71.58 [1][12]. 88 clients.'

    expect(figuresToHighlight(answer)).toEqual(['1,78,650', '1,62,990', '71.58'])
  })

  it('lists a repeated figure once and ignores labels such as FY26', () => {
    expect(figuresToHighlight('33,986 in FY26, again 33,986.')).toEqual(['33,986'])
  })
})
