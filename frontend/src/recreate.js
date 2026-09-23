// Settings Microsandbox can only change by re-creating the sandbox (network,
// workspace folders); see RecreateEditor.vue and _recreate() in app.py.

/** Message after saving; `label` names what was changed, e.g. 'Network'. */
export function savedMessage(label, result) {
  if (!result.changed) return 'No changes.'
  return result.restarted
    ? `${label} applied. The sandbox was rebuilt and is running again; the shell reconnects.`
    : `${label} applied. The sandbox was rebuilt and is stopped again.`
}
