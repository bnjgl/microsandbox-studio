// Network settings as the Python bridge expects them (see network.py):
// { mode, profiles, rules: [{ action, target, protocol, port }], ports: [{ host_port, guest_port, protocol, bind }] }
// https://docs.microsandbox.dev/networking/overview
import { count } from './util.js'

export const MODES = [
  { value: 'none', title: 'No network', text: 'Blocks incoming and outgoing traffic. The terminal and file copies keep working.' },
  { value: 'restricted', title: 'Restricted', text: 'Only the selected zones and custom rules. Microsandbox default: internet.' },
  { value: 'all', title: 'Unrestricted', text: 'Everything allowed, including the local network, the host computer and cloud metadata.' },
]
export const PROFILES = [
  { value: 'public', title: 'Internet', text: 'Public addresses' },
  { value: 'private', title: 'Local network', text: '10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 …' },
  { value: 'host', title: 'Host computer', text: 'Services on this computer via host.microsandbox.internal' },
]
export const ACTIONS = [{ value: 'allow', title: 'Allow' }, { value: 'deny', title: 'Block' }]
export const PROTOCOLS = [{ value: '', title: 'All' }, { value: 'tcp', title: 'TCP' }, { value: 'udp', title: 'UDP' }]
export const BINDS = ['127.0.0.1', '0.0.0.0']
const LOCAL_BINDS = ['127.0.0.1', '::1']

export const defaultNetwork = () => ({ mode: 'restricted', profiles: ['public'], rules: [], ports: [] })
export const newRule = () => ({ action: 'allow', target: '', protocol: '', port: '' })
export const newPort = () => ({ host_port: '', guest_port: '', protocol: 'tcp', bind: '127.0.0.1' })

const number = value => /^\d+$/.test(String(value).trim()) ? Number(value) : value
const toRule = r => ({ action: r.action, target: r.target.trim().toLowerCase(), protocol: r.protocol, port: String(r.port).trim() })
const toPort = p => ({ host_port: number(p.host_port), guest_port: number(p.guest_port), protocol: p.protocol, bind: String(p.bind || '127.0.0.1').trim() })

/** Form values to settings; the bridge validates everything again. */
export function toSettings(form) {
  const restricted = form.mode === 'restricted'
  return {
    mode: form.mode,
    profiles: restricted ? PROFILES.map(p => p.value).filter(p => form.profiles.includes(p)) : [],
    rules: restricted ? form.rules.map(toRule) : [],
    ports: form.ports.map(toPort),
  }
}

/** Whether a port binding is reachable from other devices. */
export const exposes = ports => ports.some(port => !LOCAL_BINDS.includes(String(port.bind).trim()))

/** Restricted without profile and without allow rule: nothing can go out. */
export const blocksEverything = form => !form.profiles.length && !form.rules.some(rule => rule.action === 'allow')

export function networkSummary(settings) {
  if (!settings) return 'Custom configuration'
  const access = settings.mode === 'restricted'
    ? PROFILES.filter(p => settings.profiles.includes(p.value)).map(p => p.title).join(' + ') || 'Custom rules only'
    : MODES.find(m => m.value === settings.mode).title
  return [
    access,
    settings.rules.length && count(settings.rules.length, 'rule', 'rules'),
    settings.ports.length && count(settings.ports.length, 'port', 'ports'),
  ].filter(Boolean).join(' · ')
}
