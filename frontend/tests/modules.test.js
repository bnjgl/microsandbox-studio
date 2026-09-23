import assert from 'node:assert/strict'
import { test } from 'node:test'
import { blocksEverything, defaultNetwork, exposes, networkSummary, toSettings } from '../src/network.js'
import { savedMessage } from '../src/recreate.js'
import { byTitle, recreated, withTitle } from '../src/titles.js'
import { cellAt, osc52Text, searchLabel, wheelDistance, wheelReport, wheelStep } from '../src/terminal.js'
import { statusText } from '../src/status.js'
import { neighbor, switchStep } from '../src/switcher.js'
import { TOOLS, matchesTool } from '../src/tools.js'
import { addFolders, workspaceSummary, workspaceTarget } from '../src/workspaces.js'

test('toSettings drops rules outside restricted mode and parses ports', () => {
  const form = {
    mode: 'all', profiles: ['host', 'public'], rules: [{ action: 'deny', target: ' X.com ', protocol: '', port: ' 80 ' }],
    ports: [{ host_port: ' 8080 ', guest_port: 'abc', protocol: 'tcp', bind: '' }],
  }
  assert.deepEqual(toSettings(form), {
    mode: 'all', profiles: [], rules: [], ports: [{ host_port: 8080, guest_port: 'abc', protocol: 'tcp', bind: '127.0.0.1' }],
  })
  assert.deepEqual(toSettings({ ...form, mode: 'restricted' }).profiles, ['public', 'host'])
  assert.deepEqual(toSettings({ ...form, mode: 'restricted' }).rules, [{ action: 'deny', target: 'x.com', protocol: '', port: '80' }])
})

test('network summary and warnings', () => {
  assert.equal(networkSummary(defaultNetwork()), 'Internet')
  assert.equal(networkSummary({ mode: 'restricted', profiles: [], rules: [{}], ports: [{}, {}] }), 'Custom rules only · 1 rule · 2 ports')
  assert.equal(networkSummary({ mode: 'none', profiles: [], rules: [], ports: [] }), 'No network')
  assert.equal(networkSummary(null), 'Custom configuration')
  assert.equal(exposes([{ bind: ' ::1 ' }]), false)
  assert.equal(exposes([{ bind: '0.0.0.0' }]), true)
  assert.equal(blocksEverything({ profiles: [], rules: [{ action: 'deny' }] }), true)
})

test('withTitle sets, cleans and removes display names', () => {
  const sandbox = { id: 'i', name: 'dev' }
  assert.deepEqual(withTitle({}, sandbox, '  My   box '), { i: 'My box' })
  assert.deepEqual(withTitle({ i: 'x', j: 'y' }, sandbox, 'dev'), { j: 'y' })
  assert.deepEqual(withTitle({ i: 'x' }, sandbox, ''), {})
  assert.throws(() => withTitle({}, sandbox, 'x'.repeat(129)), /at most 128/)
})

test('recreated finds renamed sandboxes whose id changed', () => {
  const known = [{ id: '1', name: 'a', title: 'Alpha' }, { id: '2', name: 'b', title: 'b' }]
  const fresh = [{ id: '9', name: 'a' }, { id: '8', name: 'b' }, { id: '3', name: 'c' }]
  assert.deepEqual(recreated(known, fresh), [[known[0], fresh[0]]])
  assert.deepEqual([{ title: 'b' }, { title: 'Áb' }, { title: 'aa' }].sort(byTitle).map(s => s.title), ['aa', 'Áb', 'b'])
})

test('osc52Text decodes copy requests and refuses reads', () => {
  assert.equal(osc52Text(`c;${btoa('hi')}`), 'hi')
  assert.equal(osc52Text('c;?'), null)
  assert.equal(osc52Text('c'), null)
  assert.equal(osc52Text('c;%%%'), null)
})

test('wheel reports carry fractions to the next event', () => {
  const first = wheelStep(0, wheelDistance({ deltaMode: 0, deltaY: 30 }, 20, 24))
  assert.equal(first.lines, 0)
  const second = wheelStep(first.rest, wheelDistance({ deltaMode: 1, deltaY: 1 }, 20, 24))
  assert.equal(second.lines, 1)
  const cell = cellAt({ clientX: 25, clientY: -5 }, { left: 0, top: 0, width: 100, height: 240 }, 10, 24)
  assert.deepEqual(cell, { col: 3, row: 1 })
  assert.equal(wheelReport(-2, cell), '\x1b[<64;3;1M\x1b[<64;3;1M')
})

test('searchLabel', () => {
  assert.equal(searchLabel(null), '')
  assert.equal(searchLabel({ resultCount: 0 }), '0/0')
  assert.equal(searchLabel({ resultCount: 5, resultIndex: 1 }), '2/5')
})

test('workspace targets get a free numbered name', () => {
  const folders = addFolders([], ['/home/u/app', '/srv/app', '/home/u/app', '/'])
  assert.deepEqual(folders.map(f => f.target), ['/workspaces/app', '/workspaces/app-2', '/workspaces/workspace'])
  assert.equal(workspaceTarget('/x/app/', folders), '/workspaces/app-3')
})

test('Windows folders are named by their last segment', () => {
  const folders = addFolders([], ['C:\\Users\\me\\proj', 'D:\\', '\\\\server\\share\\proj', 'E:/data/app'])
  assert.deepEqual(folders.map(f => f.target), ['/workspaces/proj', '/workspaces/workspace', '/workspaces/proj-2', '/workspaces/app'])
  // On macOS and Linux a backslash or a trailing colon is part of the name.
  assert.equal(workspaceTarget('/home/me/a\\b', []), '/workspaces/a\\b')
  assert.equal(workspaceTarget('/home/me/C:', []), '/workspaces/C:')
})

test('status text', () => {
  assert.equal(statusText('paused'), 'Paused')
  assert.equal(statusText('stopped'), 'Stopped')
  assert.equal(statusText('booting'), 'booting')
})

test('workspace summary and saved message after re-creating', () => {
  assert.equal(workspaceSummary([]), 'None')
  assert.equal(workspaceSummary(addFolders([], ['/a', '/b'])), '2 folders')
  assert.equal(savedMessage('Network', { changed: false }), 'No changes.')
  assert.match(savedMessage('Workspace folders', { changed: true, restarted: false }), /^Workspace folders applied\..*stopped again\.$/)
})

test('switching stops at both ends of the list', () => {
  const sandboxes = [{ name: 'a' }, { name: 'b' }, { name: 'c' }]
  assert.equal(neighbor(sandboxes, 'b', -1), 'a')
  assert.equal(neighbor(sandboxes, 'b', 1), 'c')
  assert.equal(neighbor(sandboxes, 'a', -1), null)
  assert.equal(neighbor(sandboxes, 'c', 1), null)
  assert.equal(neighbor(sandboxes, null, 1), null)
  assert.equal(switchStep({ key: 'Tab', ctrlKey: true }), 1)
  assert.equal(switchStep({ key: 'Tab', ctrlKey: true, shiftKey: true }), -1)
  assert.equal(switchStep({ key: 'Tab', ctrlKey: true, metaKey: true }), 0)
  assert.equal(switchStep({ key: 'Tab' }), 0)
})

test('install tools are found by name, keywords and several words', () => {
  const found = query => TOOLS.filter(tool => matchesTool(tool, query)).map(tool => tool.name)
  assert.ok(found('claude').includes('Claude Code'))
  assert.ok(found('codex-cli').includes('Codex CLI'))
  assert.ok(found('NODE').includes('Node.js'))
  assert.deepEqual(found('astral python'), ['uv', 'Ruff'])
  assert.equal(found('').length, TOOLS.length)
  assert.equal(new Set(TOOLS.map(tool => tool.name)).size, TOOLS.length)
})
