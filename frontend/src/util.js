// Small pure helpers shared by the modules.

// JSON round trip instead of structuredClone: settings often arrive as Vue
// proxies, which structuredClone rejects.
export const clone = value => JSON.parse(JSON.stringify(value))
export const sameJson = (a, b) => JSON.stringify(a) === JSON.stringify(b)
export const fail = message => { throw new Error(message) }
export const count = (n, one, many) => `${n} ${n === 1 ? one : many}`
