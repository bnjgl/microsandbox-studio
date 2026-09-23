// Environment variables and secrets in the sandbox YAML shape documented at
// https://docs.microsandbox.dev/sandboxes/secrets#yaml-configuration and
// https://docs.microsandbox.dev/cli/configuration#secrets.
//
// Settings are always kept normalized: every secret carries all fields, and a
// secret value of '' means "host variable with the same name" (`${KEY}`).
//
// The defaults come from the backend (environment.defaults() in Python), so
// everything that fills them in is created by environment(defaults).
import { Document, isAlias, isScalar, parseAllDocuments, visit } from 'yaml'
import { clone, count, fail, sameJson } from './util.js'

export const VIOLATION_ACTIONS = [
  { title: 'Block and log', value: 'block-and-log' },
  { title: 'Block', value: 'block' },
  { title: 'Block and stop the sandbox', value: 'block-and-terminate' },
]
export const CREATE_ONLY_FIELDS = ['substitution', 'passthrough', 'violation_action', 'require_tls_identity']
const KEY = /^[A-Za-z_][A-Za-z0-9_]*$/

export const summary = settings => `${count(Object.keys(settings.env).length, 'variable', 'variables')} · ${count(Object.keys(settings.secrets).length, 'secret', 'secrets')}`

/** Whether saving restarts a sandbox: only new secrets need a restart. */
export const needsRestart = (settings, original, status) =>
  status === 'running' && Object.keys(settings.secrets).some(key => !Object.hasOwn(original.secrets, key))

export function savedMessage(result, status) {
  if (result.restarted) return 'Saved and restarted the sandbox. The shell reconnects.'
  if (status !== 'running') return 'Saved. The configuration applies from the next start.'
  if (result.environment_changed) return 'Saved. New variables apply to new processes; type exit in the shell and press Enter to open a new one.'
  return 'Saved.'
}

// Validation helpers without defaults

const isMap = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const isAction = value => VIOLATION_ACTIONS.some(action => action.value === value)
const mapEntries = (object, transform) => Object.fromEntries(Object.entries(object).map(([key, value]) => [key, transform(key, value)]))

function mapping(value, where) {
  if (value == null) return {}
  return isMap(value) ? value : fail(`${where} must be a mapping NAME: ….`)
}
function onlyFields(value, allowed, where) {
  const unknown = Object.keys(value).filter(field => !allowed.includes(field))
  if (unknown.length) fail(`${where}: unknown field ${unknown.join(', ')}.`)
}
function checkKey(key) {
  if (!KEY.test(key)) fail(`Invalid name "${key}": letters, digits and _ only, not starting with a digit.`)
}
function hosts(value, where) {
  if (!Array.isArray(value) || value.some(host => typeof host !== 'string' || !host.trim())) fail(`${where} must be a list of hosts.`)
  return value.map(host => host.trim())
}
function envValue(key, value) {
  checkKey(key)
  if (value !== null && !['string', 'number', 'boolean'].includes(typeof value)) fail(`env.${key}: value must be text.`)
  return value === null ? '' : String(value)
}

// Rows need stable ids as Vue keys, so this counter is the one piece of module state.
let nextRowId = 0

/**
 * Settings functions for the given defaults:
 * { secret: { value, allow, substitution, … }, secret_violation_action }.
 */
export function environment(defaults) {
  // A fresh copy each time: rows are edited in place by v-model.
  const secretDefaults = () => clone(defaults.secret)
  const defaultAction = defaults.secret_violation_action
  const locations = Object.keys(defaults.secret.substitution)

  const emptySettings = () => ({ env: {}, secrets: {}, secret_violation_action: defaultAction })

  function secretValue(key, value, env) {
    const where = `secrets.${key}`
    checkKey(key)
    if (Object.hasOwn(env, key)) fail(`${key} is both a variable and a secret.`)
    const given = mapping(value, where)
    onlyFields(given, Object.keys(defaults.secret), where)
    const secret = { ...secretDefaults(), ...given }
    const text = secret.value ?? ''
    if (typeof text !== 'string') fail(`${where}.value must be text.`)
    const allow = hosts(secret.allow, `${where}.allow`)
    if (!allow.length) fail(`${where}: enter at least one allowed host (allow).`)
    const passthrough = hosts(secret.passthrough, `${where}.passthrough`)
    const substitution = mapping(secret.substitution, `${where}.substitution`)
    onlyFields(substitution, locations, `${where}.substitution`)
    const merged = { ...secretDefaults().substitution, ...substitution }
    if (Object.values(merged).some(enabled => typeof enabled !== 'boolean')) fail(`${where}.substitution expects true/false.`)
    if (typeof secret.require_tls_identity !== 'boolean') fail(`${where}.require_tls_identity expects true/false.`)
    if (secret.violation_action !== null && !isAction(secret.violation_action)) fail(`${where}.violation_action: invalid action.`)
    return { ...secret, value: text === `\${${key}}` ? '' : text, allow, passthrough, substitution: merged }
  }

  /** Validate plain data in YAML shape and fill in defaults. Throws on the first problem. */
  function normalize(data) {
    data = mapping(data, 'The configuration')
    onlyFields(data, ['env', 'secrets', 'secret_violation_action'], 'Konfiguration')
    const action = data.secret_violation_action ?? defaultAction
    if (!isAction(action)) fail('secret_violation_action: invalid action.')
    const env = mapEntries(mapping(data.env, 'env'), envValue)
    const secrets = mapEntries(mapping(data.secrets, 'secrets'), (key, value) => secretValue(key, value, env))
    return { env, secrets, secret_violation_action: action }
  }

  /** Parse YAML with the same restrictions as the microsandbox config loader. */
  function parseYaml(text) {
    const documents = parseAllDocuments(text, { uniqueKeys: true })
    if (documents.length > 1) fail('Only one YAML document is allowed.')
    const [document] = documents
    if (!document) return emptySettings()
    const problem = document.errors[0] ?? document.warnings[0]
    if (problem) fail(problem.message)
    visit(document, {
      Node(_, node) {
        if (isAlias(node) || node.anchor) fail('Anchors, aliases and merge keys are not allowed.')
      },
      Pair(_, { value }) {
        if (isScalar(value) && value.type === 'PLAIN' && /^(yes|no|on|off)$/i.test(value.value)) {
          fail(`Please put "${value.value}" in quotes.`)
        }
      },
    })
    return normalize(document.toJS())
  }

  /** A secret without the fields that have their default value; allow is always required. */
  const sparseSecret = secret => Object.fromEntries(
    Object.entries(secret).filter(([field, value]) => field === 'allow' || !sameJson(value, defaults.secret[field])),
  )

  /** Sparse YAML: only fields that differ from the documented defaults. */
  function toYaml(settings) {
    const secrets = Object.entries(settings.secrets)
    const data = {
      ...(Object.keys(settings.env).length ? { env: settings.env } : {}),
      ...(settings.secret_violation_action !== defaultAction ? { secret_violation_action: settings.secret_violation_action } : {}),
      ...(secrets.length ? { secrets: Object.fromEntries(secrets.map(([key, secret]) => [key, sparseSecret(secret)])) } : {}),
    }
    if (!Object.keys(data).length) return ''
    const document = new Document(data)
    visit(document, { Seq(_, seq) { seq.flow = true } })
    return document.toString({ lineWidth: 0, defaultStringType: 'QUOTE_DOUBLE', defaultKeyType: 'PLAIN', flowCollectionPadding: false })
  }

  const newRow = kind => ({ ...secretDefaults(), id: nextRowId++, kind, key: '' })

  /** Flatten settings into editable form rows (variables first, then secrets). */
  function toRows(settings) {
    const { env, secrets } = clone(settings)
    return [
      ...Object.entries(env).map(([key, value]) => ({ ...newRow('env'), key, value })),
      ...Object.entries(secrets).map(([key, secret]) => ({ ...newRow('secret'), ...secret, key })),
    ]
  }

  function fromRows(rows, secretViolationAction) {
    const filled = rows.filter(({ key, value, allow }) => key || value || allow.length)
    filled.forEach(({ key }, index) => {
      if (!key) fail('Every entry needs a name.')
      if (filled.findIndex(row => row.key === key) < index) fail(`${key} appears twice.`)
    })
    const variables = filled.filter(row => row.kind !== 'secret')
    const secrets = filled.filter(row => row.kind === 'secret')
    return normalize({
      env: Object.fromEntries(variables.map(({ key, value }) => [key, value])),
      secrets: Object.fromEntries(secrets.map(({ id, kind, key, ...secret }) => [key, secret])),
      secret_violation_action: secretViolationAction,
    })
  }

  /** Fields the Python SDK can only set at creation time. Returns an error message or ''. */
  function createOnlyChange(settings, original) {
    if (settings.secret_violation_action !== original.secret_violation_action) {
      return 'secret_violation_action can only be set on creation.'
    }
    const changes = Object.entries(settings.secrets).flatMap(([key, secret]) => {
      const before = original.secrets[key] ?? defaults.secret
      return CREATE_ONLY_FIELDS.filter(field => !sameJson(secret[field], before[field])).map(field => `${key}: ${field} can only be set on creation.`)
    })
    return changes[0] ?? ''
  }

  return { locations, emptySettings, normalize, parseYaml, toYaml, newRow, toRows, fromRows, createOnlyChange }
}
