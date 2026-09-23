<script setup>
// Interactive shell for one sandbox. App keeps one terminal per opened sandbox
// and only hides inactive ones, so sessions survive switching sandboxes.
// A running sandbox is connected automatically.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { Unicode11Addon } from '@xterm/addon-unicode11'
import { SearchAddon } from '@xterm/addon-search'
import { ProgressAddon } from '@xterm/addon-progress'
import '@xterm/xterm/css/xterm.css'
import { api, newToken, terminalHandlers } from '../api'
import { WHEEL_TRACKING, bytes, cellAt, osc52Text, searchLabel, wheelDistance, wheelReport, wheelStep } from '../terminal'

const props = defineProps({ sandbox: { type: String, required: true }, running: Boolean, active: Boolean })
const emit = defineEmits(['error', 'progress'])

const node = ref(null), token = ref(null), connecting = ref(false)
const searching = ref(false), query = ref(''), results = ref(null), searchField = ref(null)
// Links open in the host browser: the webview can't, and the sandbox has none.
const openUrl = (_event, url) => api().open_url(url).catch(e => emit('error', String(e)))
const term = new Terminal({ allowProposedApi: true, linkHandler: { activate: openUrl }, cursorBlink: true, macOptionClickForcesSelection: true, fontSize: 14, lineHeight: 1.3, theme: { background: '#090F1C', foreground: '#D7E4F2', cursor: '#75E1C2' } })
const fit = new FitAddon()
term.loadAddon(fit)
term.loadAddon(new WebLinksAddon(openUrl))
term.loadAddon(new Unicode11Addon())
term.unicode.activeVersion = '11' // widths of emoji and symbols as current CLIs expect
const search = new SearchAddon()
term.loadAddon(search)
search.onDidChangeResults(r => { results.value = r })
// OSC 9;4 progress (state 0 = none), shown next to the sandbox in the list.
const progress = new ProgressAddon()
term.loadAddon(progress)
progress.onChange(p => emit('progress', p))
let observer, inputQueue = Promise.resolve(), nextInput = null

const write = encoded => term.write(bytes(encoded))
const copy = text => api().copy_to_clipboard(text).catch(e => emit('error', String(e)))

// OSC 52 from programs in the sandbox (e.g. "c to copy").
term.parser.registerOscHandler(52, data => {
  const text = osc52Text(data)
  if (text !== null) copy(text)
  return true
})
// Apps with mouse reporting (e.g. Claude Code) get at most one wheel report per
// event from xterm, damped to 30% for small trackpad deltas, which makes momentum
// scrolling slow down abruptly. Report every line scrolled instead, in proportion
// to the delta. Only for SGR encoding (DECSET 1006), which such apps request.
let sgrMouse = false, wheelRest = 0
for (const [final, on] of [['h', true], ['l', false]]) {
  term.parser.registerCsiHandler({ prefix: '?', final }, params => {
    if (params.includes(1006)) sgrMouse = on
    return false // xterm still applies the mode itself
  })
}
term.attachCustomWheelEventHandler(e => {
  if (!sgrMouse || !WHEEL_TRACKING.includes(term.modes.mouseTrackingMode)) return true
  const screen = node.value.querySelector('.xterm-screen').getBoundingClientRect()
  const step = wheelStep(wheelRest, wheelDistance(e, screen.height / term.rows, term.rows))
  wheelRest = step.rest
  if (step.lines) term.input(wheelReport(step.lines, cellAt(e, screen, term.cols, term.rows)), false)
  return false
})

// Cmd+C (macOS) or Ctrl+Shift+C copies the selection; Ctrl+C stays SIGINT.
// Cmd+F or Ctrl+Shift+F opens the search; Ctrl+F stays with the shell.
term.attachCustomKeyEventHandler(e => {
  if (e.type !== 'keydown' || !(e.metaKey || e.ctrlKey && e.shiftKey)) return true
  if (e.code === 'KeyC' && term.hasSelection()) copy(term.getSelection())
  else if (e.code === 'KeyF') openSearch()
  else return true
  return false
})

const searchOptions = { decorations: { matchOverviewRuler: '#75E1C2', activeMatchColorOverviewRuler: '#FFD166', matchBackground: '#1F4E5A', activeMatchBackground: '#8A6D1F' } }
function find(backwards = false) {
  if (!query.value) { search.clearDecorations(); results.value = null; return }
  search[backwards ? 'findPrevious' : 'findNext'](query.value, searchOptions)
}
async function openSearch() {
  searching.value = true
  await nextTick(); searchField.value?.select()
}
function closeSearch() {
  searching.value = false; search.clearDecorations(); results.value = null; term.focus()
}

// Sessions closed by close() are unregistered first, so this only sees shells
// that ended on their own (exit, stop or restart of the sandbox).
function handle(id, event, { data, message }) {
  if (event === 'terminal-data') write(data)
  else if (event === 'terminal-error') emit('error', message)
  else if (event === 'terminal-closed') {
    terminalHandlers.delete(id)
    if (token.value === id) token.value = null
    term.writeln(props.running ? '\r\nShell ended. Press Enter to open a new shell.' : '\r\nConnection closed.')
  }
}

term.onData(data => {
  if (token.value) send(data)
  else if (data === '\r') connect()
})

function send(data) {
  const active = token.value
  // Input arriving while a write is pending (fast typing, mouse wheel reports)
  // joins the next write instead of queueing one bridge call each.
  if (nextInput?.token === active) { nextInput.data += data; return }
  const input = nextInput = { token: active, data }
  inputQueue = inputQueue.then(() => {
    if (nextInput === input) nextInput = null
    return api().write_terminal(active, input.data)
  }).catch(e => emit('error', String(e)))
}

// Types a command into the shell and runs it, e.g. from the install menu.
function run(command) {
  if (!token.value) { emit('error', 'The shell is not connected.'); return }
  send(`${command}\r`); term.focus()
}

async function connect() {
  if (token.value || connecting.value || !props.running) return
  connecting.value = true
  const id = newToken()
  terminalHandlers.set(id, (event, payload) => handle(id, event, payload))
  term.reset(); term.write('Verbinde …\r')
  try {
    await api().open_terminal(props.sandbox, id, term.cols, term.rows)
    // The shell may already have ended while open_terminal was running.
    if (terminalHandlers.has(id)) token.value = id
    if (props.active) term.focus()
  } catch (e) {
    terminalHandlers.delete(id)
    term.writeln('\r\nConnection failed. Press Enter to try again.')
    emit('error', String(e))
  } finally { connecting.value = false }
}

async function close() {
  const active = token.value
  if (!active) return
  token.value = null
  terminalHandlers.delete(active)
  await inputQueue
  try { await api().close_terminal(active) } catch (e) { emit('error', String(e)) }
}

async function reconnect() { await close(); await connect() }
defineExpose({ close, reconnect, run })

watch(() => props.running, running => { running ? connect() : close() })
watch(() => props.active, async active => {
  if (!active) return
  await nextTick(); fit.fit(); term.focus()
})

onMounted(() => {
  term.open(node.value); fit.fit()
  observer = new ResizeObserver(() => {
    if (!node.value?.offsetWidth) return // hidden while another sandbox is shown
    fit.fit()
    if (token.value) api().resize_terminal(token.value, term.cols, term.rows).catch(() => {})
  })
  observer.observe(node.value)
  connect()
})
onBeforeUnmount(() => { observer?.disconnect(); close(); term.dispose() })
</script>

<template>
  <v-sheet color="#090F1C" class="position-absolute pa-4" style="inset: 0">
    <div ref="node" class="h-100 w-100" />
    <v-card v-if="searching" class="position-absolute d-flex align-center ga-1 pa-1" style="top: 8px; right: 24px; z-index: 5" color="surface" border rounded="lg" elevation="4">
      <v-text-field
        ref="searchField" v-model="query" density="compact" variant="solo-filled" flat hide-details single-line autofocus
        placeholder="Search" prepend-inner-icon="mdi-magnify" style="width: 220px"
        @update:model-value="find()" @keydown.enter.exact.prevent="find()" @keydown.shift.enter.prevent="find(true)" @keydown.esc.prevent="closeSearch"
      />
      <span class="text-caption text-medium-emphasis px-1" style="min-width: 48px">{{ searchLabel(results) }}</span>
      <v-btn icon="mdi-chevron-up" variant="text" size="small" aria-label="Previous match" @click="find(true)" />
      <v-btn icon="mdi-chevron-down" variant="text" size="small" aria-label="Next match" @click="find()" />
      <v-btn icon="mdi-close" variant="text" size="small" aria-label="Close search" @click="closeSearch" />
    </v-card>
  </v-sheet>
</template>
