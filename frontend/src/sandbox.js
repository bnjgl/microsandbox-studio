export const count = (n, one, many) => `${n} ${n === 1 ? one : many}`

const STATUS_TEXT = { running: 'Running', stopped: 'Stopped', paused: 'Paused' }

export const statusText = status => STATUS_TEXT[status] || status
export const statusColor = status => status === 'running' ? 'primary' : 'secondary'

export const CPU_CHOICES = [1, 2, 4, 8, 16]
export const MEMORY_CHOICES = [512, 1024, 2048, 4096, 8192, 16384]

export const resourcesSummary = ({ cpus, memory }) => `${count(cpus ?? 1, 'CPU', 'CPUs')} · ${memory ?? '—'} MiB`

export const MODES = [
  { value: 'none', title: 'No network', text: 'Blocks incoming and outgoing traffic.' },
  { value: 'internet', title: 'Internet', text: 'Public internet only. Microsandbox default.' },
  { value: 'all', title: 'Unrestricted', text: 'Also the local network, the host computer and cloud metadata.' },
]

export const defaultNetwork = () => ({ mode: 'internet', ports: [] })
export const newPort = () => ({ host: '', guest: '' })

const modeOf = mode => MODES.find(m => m.value === mode)

export const modeDescription = mode => modeOf(mode) ? `${modeOf(mode).title}: ${modeOf(mode).text}` : 'Custom policy, set outside the app.'

export const networkSummary = ({ mode, ports }) => [
  modeOf(mode)?.title ?? 'Custom policy',
  ports.length && count(ports.length, 'port', 'ports'),
].filter(Boolean).join(' · ')

const SANDBOX_NAME = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/
const VARIABLE_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/

export const required = value => !!String(value ?? '').trim() || 'Required'
export const sandboxName = value => SANDBOX_NAME.test(value) || 'Letters, digits, dots, dashes and underscores'
export const variableName = value => VARIABLE_NAME.test(value) || 'Letters, digits and underscores, not starting with a digit'
export const portNumber = value => (Number.isInteger(value) && value >= 1 && value <= 65535) || 'From 1 to 65535'
export const hosts = value => value.split(',').some(host => host.trim()) || 'At least one host'
export const once = (values, message) => value => values.filter(other => other === value).length < 2 || message

export const emptyRows = () => ({ variables: [], secrets: [] })
export const newVariable = () => ({ name: '', value: '' })
export const newSecret = () => ({ name: '', value: '', allow: '' })

export const toRows = settings => ({
  variables: Object.entries(settings.env).map(([name, value]) => ({ name, value })),
  secrets: Object.entries(settings.secrets).map(([name, secret]) => ({ name, value: secret.value, allow: secret.allow.join(', ') })),
})

export const fromRows = ({ variables, secrets }) => ({
  env: Object.fromEntries(variables.filter(row => row.name.trim()).map(row => [row.name.trim(), row.value])),
  secrets: Object.fromEntries(secrets.filter(row => row.name.trim()).map(row => [
    row.name.trim(),
    { value: row.value, allow: row.allow.split(',').map(host => host.trim()).filter(Boolean) },
  ])),
})

export const environmentSummary = ({ variables, secrets }) =>
  `${count(variables, 'variable', 'variables')} · ${count(secrets, 'secret', 'secrets')}`

export const workspaceSummary = folders => folders.length ? count(folders.length, 'folder', 'folders') : 'None'
