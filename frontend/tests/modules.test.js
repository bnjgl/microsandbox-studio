import assert from 'node:assert/strict'
import { test } from 'node:test'
import { defaultNetwork, emptyRows, environmentSummary, fromRows, hosts, modeDescription, networkSummary, once, portNumber, required, resourcesSummary, sandboxName, statusText, toRows, variableName, workspaceSummary } from '../src/sandbox.js'

test('environment rows round trip and skip rows without a name', () => {
  const settings = { env: { MODE: 'dev' }, secrets: { TOKEN: { value: '', allow: ['a.com', 'b.com'] } } }
  const rows = toRows(settings)
  assert.deepEqual(rows.secrets, [{ name: 'TOKEN', value: '', allow: 'a.com, b.com' }])
  assert.deepEqual(fromRows(rows), settings)
  assert.deepEqual(fromRows({ variables: [{ name: ' ', value: 'x' }, { name: ' A ', value: '1' }], secrets: [] }), { env: { A: '1' }, secrets: {} })
  assert.deepEqual(fromRows(emptyRows()), { env: {}, secrets: {} })
})

test('resources summary', () => {
  assert.equal(resourcesSummary({ cpus: 2, memory: 1024 }), '2 CPUs · 1024 MiB')
  assert.equal(resourcesSummary({}), '1 CPU · — MiB')
})

test('environment summary', () => {
  assert.equal(environmentSummary({ variables: 1, secrets: 0 }), '1 variable · 0 secrets')
})

test('network summary and description', () => {
  assert.equal(networkSummary(defaultNetwork()), 'Internet')
  assert.equal(modeDescription('none'), 'No network: Blocks incoming and outgoing traffic.')
  assert.equal(modeDescription('custom'), 'Custom policy, set outside the app.')
  assert.equal(networkSummary({ mode: 'custom', ports: [{ host: 1, guest: 2 }] }), 'Custom policy · 1 port')
})

test('workspace summary', () => {
  assert.equal(workspaceSummary([]), 'None')
  assert.equal(workspaceSummary([{ source: '/a', target: '/workspaces/a' }, { source: '/b', target: '/workspaces/b' }]), '2 folders')
})

test('status text', () => {
  assert.equal(statusText('paused'), 'Paused')
  assert.equal(statusText('booting'), 'booting')
})

test('form rules', () => {
  assert.equal(sandboxName('dev-1.x'), true)
  assert.equal(typeof sandboxName('my box'), 'string')
  assert.equal(variableName('API_KEY'), true)
  assert.equal(typeof variableName('1KEY'), 'string')
  assert.equal(portNumber(8080), true)
  assert.equal(typeof portNumber(70000), 'string')
  assert.equal(typeof portNumber(''), 'string')
  assert.equal(typeof required(' '), 'string')
  assert.equal(typeof hosts(' , '), 'string')
  assert.equal(once([1, 2], 'x')(1), true)
  assert.equal(once([1, 1], 'x')(1), 'x')
})
