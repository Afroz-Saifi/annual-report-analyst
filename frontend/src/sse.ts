export type SseEvent = { event: string; data: string }

/**
 * Turns a stream of text into server-sent events. Text arrives in arbitrary
 * pieces, so an event is only emitted once its closing blank line has arrived.
 */
export function createSseParser(onEvent: (event: SseEvent) => void) {
  let buffer = ''
  return {
    push(text: string) {
      buffer = (buffer + text).replace(/\r\n/g, '\n')
      let end = buffer.indexOf('\n\n')
      while (end !== -1) {
        const block = buffer.slice(0, end)
        buffer = buffer.slice(end + 2)
        const event = parseBlock(block)
        if (event) onEvent(event)
        end = buffer.indexOf('\n\n')
      }
    },
  }
}

function parseBlock(block: string): SseEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  return data.length ? { event, data: data.join('\n') } : null
}
