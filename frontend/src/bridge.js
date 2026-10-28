export const api = () => window.pywebview?.api

export const bridgeReady = () => new Promise(resolve => {
  const view = window.pywebview
  const ready = view?.api?.list_sandboxes && (view.platform !== 'qtwebengine' || view._QWebChannel)
  if (ready) resolve(); else window.addEventListener('pywebviewready', () => resolve(), { once: true })
})
