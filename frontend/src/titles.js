// Display names by sandbox id, kept in localStorage (pywebview persists it
// outside private mode). Microsandbox cannot rename a sandbox, so CLI and SDK
// keep using the technical name.
const KEY = 'sandbox-titles'

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || {} } catch { return {} }
}
const save = titles => localStorage.setItem(KEY, JSON.stringify(titles))

export const titleOf = sandbox => load()[sandbox.id] || sandbox.name

/** The titles with a display name set; an empty title or the technical name removes it. */
export function withTitle(titles, sandbox, title) {
  const clean = title.trim().replace(/\s+/g, ' ')
  if (clean.length > 128) throw new Error('The name can be at most 128 characters long.')
  const { [sandbox.id]: _, ...rest } = titles
  return clean && clean !== sandbox.name ? { ...rest, [sandbox.id]: clean } : rest
}

export const setTitle = (sandbox, title) => save(withTitle(load(), sandbox, title))

/**
 * Sandboxes that were re-created under the same name (network settings) keep
 * their name but get a new id. Returns [old, fresh] pairs whose display name
 * has to move to the new id.
 */
export const recreated = (known, fresh) => fresh.flatMap(sandbox => {
  const old = known.find(o => o.name === sandbox.name)
  return old && old.id !== sandbox.id && old.title !== old.name ? [[old, sandbox]] : []
})

export const byTitle = (a, b) => a.title.localeCompare(b.title, 'en', { sensitivity: 'base' })
