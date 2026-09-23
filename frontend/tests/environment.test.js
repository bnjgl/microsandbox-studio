import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { test } from 'node:test'
import { environment, needsRestart, savedMessage, summary } from '../src/environment.js'

// The same defaults the app gets over the bridge, straight from the backend.
const DEFAULTS = JSON.parse(execFileSync('uv', [
  'run', '--quiet', 'python', '-c',
  'import json; from microsandbox_studio.environment import defaults; print(json.dumps(defaults()))',
], { encoding: 'utf8' }))
const { createOnlyChange, emptySettings, fromRows, newRow, normalize, parseYaml, toRows, toYaml } = environment(DEFAULTS)

const secret = fields => ({ ...structuredClone(DEFAULTS.secret), allow: ['api.github.com'], ...fields })

test('normalize fills defaults and drops a self reference', () => {
  const result = normalize({ env: { PORT: 3000 }, secrets: { TOKEN: { value: '${TOKEN}', allow: [' api.github.com '] } } })
  assert.deepEqual(result, { env: { PORT: '3000' }, secrets: { TOKEN: secret({}) }, secret_violation_action: DEFAULTS.secret_violation_action })
})

test('rows get their own copy of the defaults', () => {
  const [a, b] = [newRow('secret'), newRow('secret')]
  a.substitution.body = true
  a.allow.push('x')
  assert.equal(b.substitution.body, DEFAULTS.secret.substitution.body)
  assert.deepEqual(b.allow, [])
  assert.deepEqual(emptySettings().secret_violation_action, DEFAULTS.secret_violation_action)
})

test('normalize rejects a name used twice', () => {
  assert.throws(() => normalize({ env: { A: '1' }, secrets: { A: { allow: ['a'] } } }), /both a variable and a secret/)
})

test('YAML round trip is sparse and lossless', () => {
  const settings = normalize({ env: { MODE: 'dev' }, secrets: { TOKEN: { value: '${GH}', allow: ['a.com'], passthrough: ['b.com'] } } })
  const yaml = toYaml(settings)
  assert.equal(yaml, 'env:\n  MODE: "dev"\nsecrets:\n  TOKEN:\n    value: "${GH}"\n    allow: ["a.com"]\n    passthrough: ["b.com"]\n')
  assert.deepEqual(parseYaml(yaml), settings)
  assert.equal(toYaml(emptySettings()), '')
})

test('parseYaml rejects what the CLI loader rejects', () => {
  assert.throws(() => parseYaml('env:\n  A: yes\n'), /in quotes/)
  assert.throws(() => parseYaml('env: &x\n  A: "1"\n'), /Anchors/)
  assert.throws(() => parseYaml('a: 1\n---\nb: 2\n'), /Only one YAML document/)
})

test('rows round trip and skip blank rows', () => {
  const settings = normalize({ env: { A: '1' }, secrets: { B: { allow: ['x'] } } })
  const rows = [...toRows(settings), newRow('env')]
  assert.deepEqual(fromRows(rows, 'block-and-log'), settings)
})

test('fromRows reports duplicate and missing names', () => {
  const row = (key, value = 'v') => ({ ...newRow('env'), key, value })
  assert.throws(() => fromRows([row('A'), row('A')], 'block'), /A appears twice/)
  assert.throws(() => fromRows([row('')], 'block'), /needs a name/)
})

test('createOnlyChange names the first locked field', () => {
  const before = normalize({ secrets: { T: { allow: ['a'] } } })
  assert.equal(createOnlyChange(before, before), '')
  const after = normalize({ secrets: { T: { allow: ['a'], require_tls_identity: false } } })
  assert.equal(createOnlyChange(after, before), 'T: require_tls_identity can only be set on creation.')
})

test('only new secrets on a running sandbox need a restart', () => {
  const before = normalize({ secrets: { T: { allow: ['a'] } } })
  const after = normalize({ secrets: { T: { allow: ['b'] }, NEW: { allow: ['a'] } } })
  assert.equal(needsRestart(after, before, 'running'), true)
  assert.equal(needsRestart(after, before, 'stopped'), false)
  assert.equal(needsRestart(before, before, 'running'), false)
})

test('summary and saved message', () => {
  assert.equal(summary(normalize({ env: { A: '1' } })), '1 variable · 0 secrets')
  assert.equal(savedMessage({ restarted: false }, 'stopped'), 'Saved. The configuration applies from the next start.')
  assert.equal(savedMessage({ restarted: false, environment_changed: false }, 'running'), 'Saved.')
})
