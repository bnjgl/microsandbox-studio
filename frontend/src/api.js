import { fail } from './util'

// pywebview exposes the Python Bridge methods as promise-returning functions.
export const api = () => window.pywebview?.api

// pywebview sets `api` to an empty object first, fills in the methods and only
// then fires pywebviewready (on Qt once its web channel is up), so an existing
// `api` does not mean the bridge can be called yet.
export const bridgeReady = () => new Promise(resolve => {
  const view = window.pywebview
  const ready = view?.api?.list_sandboxes && (view.platform !== 'qtwebengine' || view._QWebChannel)
  if (ready) resolve(); else window.addEventListener('pywebviewready', () => resolve(), { once: true })
})

// Environment functions with the backend's defaults, loaded once at startup
// (see App.vue); the components that use them are only rendered afterwards.
// Imported on demand, so yaml stays out of the initial bundle.
let environmentFunctions = null
export async function loadEnvironment() {
  const [{ environment }, defaults] = await Promise.all([import('./environment'), api().environment_defaults()])
  environmentFunctions = environment(defaults)
}
export const useEnvironment = () => environmentFunctions ?? fail('The defaults are not loaded yet.')

// Run an async task while a busy flag is set; errors are written to `error`.
export async function track(busy, error, task) {
  busy.value = true; error.value = ''
  try { return await task() } catch (e) { error.value = String(e) } finally { busy.value = false }
}

// Terminal event handlers by session token. Every open terminal registers
// itself here, so several sessions can stream at the same time.
export const terminalHandlers = new Map()
// Handlers for app-wide events without a token, by event name.
export const appHandlers = new Map()
window.msbEvent = (event, payload) => payload.token
  ? terminalHandlers.get(payload.token)?.(event, payload)
  : appHandlers.get(event)?.(payload)

export const newToken = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')
