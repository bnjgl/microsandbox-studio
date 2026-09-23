// Switching to the previous or next sandbox in the list, with the header arrows
// or Ctrl+Tab / Ctrl+Shift+Tab, the common next/previous tab shortcut on every
// platform. It does not wrap around, like the arrows.

export const SHORTCUTS = { [-1]: 'Ctrl+Shift+Tab', [1]: 'Ctrl+Tab' }

/** Name of the sandbox `step` places away from `selected`, or null at either end. */
export function neighbor(sandboxes, selected, step) {
  const index = sandboxes.findIndex(sandbox => sandbox.name === selected)
  return index < 0 ? null : sandboxes[index + step]?.name ?? null
}

/** -1 or 1 for the switch shortcut, otherwise 0. */
export const switchStep = ({ key, ctrlKey, shiftKey, altKey, metaKey }) =>
  key === 'Tab' && ctrlKey && !altKey && !metaKey ? (shiftKey ? -1 : 1) : 0
