// Pure helpers for TerminalCard: byte decoding, OSC 52 and SGR mouse wheel reports.

// Lines scrolled per line of wheel distance; 1 felt too fast.
export const WHEEL_SPEED = 0.6
// Mouse tracking modes that receive wheel reports.
export const WHEEL_TRACKING = ['vt200', 'drag', 'any']

export const bytes = encoded => Uint8Array.from(atob(encoded), c => c.charCodeAt(0))

/**
 * Text an OSC 52 sequence asks to copy ("c;<base64>"), or null. Reading the
 * host clipboard ("?") is deliberately not supported.
 */
export function osc52Text(data) {
  const payload = data.split(';')[1]
  if (!payload || payload === '?') return null
  try { return new TextDecoder().decode(bytes(payload)) } catch { return null }
}

// WheelEvent.DOM_DELTA_PIXEL and DOM_DELTA_LINE; the rest is DOM_DELTA_PAGE.
const DELTA_PIXEL = 0, DELTA_LINE = 1

/** Wheel distance in terminal lines for a WheelEvent's deltaMode. */
export function wheelDistance({ deltaMode, deltaY }, cellHeight, rows) {
  if (deltaMode === DELTA_PIXEL) return deltaY / cellHeight
  if (deltaMode === DELTA_LINE) return deltaY
  return deltaY * rows
}

/** Whole lines to report now and the fraction carried to the next event. */
export function wheelStep(rest, distance) {
  const total = rest + WHEEL_SPEED * distance
  const lines = Math.trunc(total)
  return { lines, rest: total - lines }
}

const clampCell = (value, max) => Math.min(max, Math.max(1, value))

/** 1-based cell under the pointer. */
export function cellAt({ clientX, clientY }, screen, cols, rows) {
  return {
    col: clampCell(Math.ceil((clientX - screen.left) / (screen.width / cols)), cols),
    row: clampCell(Math.ceil((clientY - screen.top) / (screen.height / rows)), rows),
  }
}

/** SGR (DECSET 1006) wheel reports: button 64 scrolls up, 65 down, one per line. */
export const wheelReport = (lines, { col, row }) => `\x1b[<${lines < 0 ? 64 : 65};${col};${row}M`.repeat(Math.abs(lines))

export function searchLabel(results) {
  if (!results) return ''
  return results.resultCount ? `${results.resultIndex + 1}/${results.resultCount}` : '0/0'
}
