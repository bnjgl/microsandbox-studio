// Sandbox status as shown in the app.
const STATUS_TEXT = { running: 'Running', stopped: 'Stopped', paused: 'Paused' }

export const statusText = status => STATUS_TEXT[status] || status
export const statusColor = status => status === 'running' ? 'primary' : 'secondary'
