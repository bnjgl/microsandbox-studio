// Workspace folders, mounted at /workspaces/<name> (see workspaces.py):
// [{ source: host path, target: guest path }]
import { count } from './util.js'

// Windows paths from the folder dialog look like C:\Users\me or \\server\share.
const isWindowsPath = source => /^(?:[A-Za-z]:[\\/]|\\\\)/.test(source)

/** Last path segment; a root such as / or C:\ has none. */
function folderName(source) {
  const windows = isWindowsPath(source)
  const name = source.split(windows ? /[\\/]/ : '/').filter(Boolean).at(-1)
  const drive = windows && /^[A-Za-z]:$/.test(name)
  return name && !drive ? name : 'workspace'
}

/** First free /workspaces/<name>, /workspaces/<name>-2, … for a host folder. */
export function workspaceTarget(source, folders) {
  const name = folderName(source)
  const taken = target => folders.some(folder => folder.target === target)
  let target = `/workspaces/${name}`
  for (let suffix = 2; taken(target); suffix++) target = `/workspaces/${name}-${suffix}`
  return target
}

/** Folders with the new sources added; already chosen sources are kept once. */
export const addFolders = (folders, sources) => sources.reduce(
  (result, source) => result.some(folder => folder.source === source)
    ? result
    : [...result, { source, target: workspaceTarget(source, result) }],
  folders,
)

export const workspaceSummary = folders => folders.length ? count(folders.length, 'folder', 'folders') : 'None'
