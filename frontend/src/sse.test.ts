import { describe, expect, it } from 'vitest'
import { createSseParser } from './sse'
import type { SseEvent } from './sse'

function collect(...pieces: string[]): SseEvent[] {
  const events: SseEvent[] = []
  const parser = createSseParser((event) => events.push(event))
  for (const piece of pieces) parser.push(piece)
  return events
}

describe('createSseParser', () => {
  it('emits each complete event with its name and data', () => {
    const events = collect('event: step\ndata: {"step":"retrieve"}\n\nevent: answer\ndata: {"a":1}\n\n')

    expect(events).toEqual([
      { event: 'step', data: '{"step":"retrieve"}' },
      { event: 'answer', data: '{"a":1}' },
    ])
  })

  it('waits for the rest of an event that arrives in pieces', () => {
    const events = collect('event: st', 'ep\ndata: {"step":', '"verify"}\n', '\n')

    expect(events).toEqual([{ event: 'step', data: '{"step":"verify"}' }])
  })

  it('emits nothing until the closing blank line arrives', () => {
    expect(collect('event: step\ndata: {}\n')).toEqual([])
  })

  it('accepts carriage-return line endings', () => {
    expect(collect('event: step\r\ndata: {}\r\n\r\n')).toEqual([{ event: 'step', data: '{}' }])
  })

  it('names an event "message" when no name is given and skips comment-only blocks', () => {
    expect(collect(': keep-alive\n\ndata: hello\n\n')).toEqual([{ event: 'message', data: 'hello' }])
  })
})
