<script setup>
import { computed, defineAsyncComponent, onMounted, reactive, ref, watch } from 'vue'
import { api, appHandlers, bridgeReady, loadEnvironment } from './api'
import { statusColor, statusText } from './status'
import { SHORTCUTS, neighbor, switchStep } from './switcher'
import { byTitle, recreated, setTitle, titleOf } from './titles'
// Loaded on demand so xterm and yaml stay out of the initial bundle
const CopyDialog = defineAsyncComponent(() => import('./components/CopyDialog.vue'))
const InstallMenu = defineAsyncComponent(() => import('./components/InstallMenu.vue'))
const CreateDialog =defineAsyncComponent(() => import('./components/CreateDialog.vue'))
const SettingsDialog = defineAsyncComponent(() => import('./components/SettingsDialog.vue'))
const TerminalCard = defineAsyncComponent(() => import('./components/TerminalCard.vue'))

const sandboxes = ref([]), selected = ref(null), drawer = ref(false), loaded = ref(false)
const pending = reactive(new Set()) // running actions as 'action:sandbox'
const toast = ref({ show: false, text: '', color: '' })
const dialog = ref('') // 'create' | 'settings' | 'copy'
const renameTarget = ref(null), renameText = ref(''), deleteTarget = ref(null)
const duplicateTarget = ref(null), duplicateText = ref('')

// Every sandbox shown once keeps its terminal, so sessions survive switching.
const visited = ref(new Set())
const terminals = {}
// OSC 9;4 progress per sandbox: state 1 value, 2 error, 3 indeterminate, 4 paused.
const progress = reactive({})
const progressColor = { 2: 'error', 4: 'warning' }
const progressProps = ({ state, value }) => ({ indeterminate: state === 3, modelValue: value, color: progressColor[state] ?? 'primary', size: 16, width: 2 })
const opened = computed(() => sandboxes.value.filter(s => visited.value.has(s.name)))
const current = computed(() => sandboxes.value.find(s => s.name === selected.value))
const running = computed(() => current.value?.status === 'running')
const busy = (action, name = selected.value) => pending.has(`${action}:${name}`)

// v-model for a dialog that is open while `dialog` has its name.
const dialogModel = name => computed({ get: () => dialog.value === name, set: open => { dialog.value = open ? name : '' } })
// v-model for a dialog that is open while it has a target sandbox.
const targetModel = target => computed({ get: () => !!target.value, set: open => { if (!open) target.value = null } })
const createOpen = dialogModel('create'), settingsOpen = dialogModel('settings'), copyOpen = dialogModel('copy')
const renameOpen = targetModel(renameTarget), duplicateOpen = targetModel(duplicateTarget), deleteOpen = targetModel(deleteTarget)

watch(selected, name => { if (name) visited.value = new Set(visited.value).add(name) })

const notify = (text, color = 'success') => { toast.value = { show: true, text, color } }
const fail = e => notify(String(e), 'error')

async function run(key, task) {
  pending.add(key)
  try { await task(); await refresh() } catch (e) { fail(e) }
  finally { pending.delete(key) }
}
const reload = () => run('refresh:', () => {})

async function refresh() {
  const fresh = await api().list_sandboxes()
  for (const [old, sandbox] of recreated(sandboxes.value, fresh)) { setTitle(sandbox, old.title); setTitle(old, '') }
  sandboxes.value = fresh.map(s => ({ ...s, title: titleOf(s) })).sort(byTitle)
  loaded.value = true
  if (!current.value) selected.value = sandboxes.value[0]?.name ?? null
}

function select(name) { selected.value = name; drawer.value = false }

// Previous (-1) and next (1) sandbox for the header arrows and Ctrl+(Shift+)Tab.
const neighbors = computed(() => ({ [-1]: neighbor(sandboxes.value, selected.value, -1), [1]: neighbor(sandboxes.value, selected.value, 1) }))
const modalOpen = computed(() => dialog.value || renameOpen.value || duplicateOpen.value || deleteOpen.value || closeOpen.value)
// Capture phase, so the shortcut never reaches the terminal.
window.addEventListener('keydown', e => {
  const step = switchStep(e)
  if (!step || modalOpen.value) return
  e.preventDefault(); e.stopPropagation()
  if (neighbors.value[step]) select(neighbors.value[step])
}, true)
const start = name => run(`start:${name}`, () => api().start_sandbox(name))
const stop = name => run(`stop:${name}`, async () => { await terminals[name]?.close(); await api().stop_sandbox(name) })

function askRename(sandbox) { renameTarget.value = sandbox; renameText.value = sandbox.title }
const rename = () => run('rename:', async () => { setTitle(renameTarget.value, renameText.value); renameTarget.value = null })

function askDuplicate(sandbox) { duplicateTarget.value = sandbox; duplicateText.value = `${sandbox.name}-copy` }
const duplicate = () => run('duplicate:', async () => {
  const name = duplicateText.value.trim()
  await api().duplicate_sandbox(duplicateTarget.value.name, name)
  duplicateTarget.value = null
  select(name)
  notify('Sandbox duplicated.')
})

const remove = () => run('delete:', async () => {
  const { name } = deleteTarget.value
  await terminals[name]?.close()
  await api().delete_sandbox(name)
  setTitle(deleteTarget.value, '')
  visited.value = new Set([...visited.value].filter(n => n !== name))
  if (selected.value === name) selected.value = null
  deleteTarget.value = null
  if (dialog.value === 'settings') dialog.value = ''
})

// Closing the window with running sandboxes asks first; shpool keeps their shells alive.
const closeRunning = ref([])
const closeOpen = computed({ get: () => closeRunning.value.length > 0, set: open => { if (!open) closeRunning.value = [] } })
const closeTitles = computed(() => closeRunning.value.map(name => sandboxes.value.find(s => s.name === name)?.title ?? name))
appHandlers.set('close-requested', ({ running }) => { closeRunning.value = running })
const quit = (stop = false) => run(stop ? 'quit:stop' : 'quit:', () => api().quit(stop ? closeRunning.value : []))

function created(name) { select(name); reload() }
function saved(message, result) {
  notify(message)
  const name = selected.value
  // A re-created sandbox gets a new id, so its terminal is mounted anew and connects itself.
  run('refresh:', async () => { if (result?.restarted && !result.recreated) await terminals[name]?.reconnect() })
}

// The dialogs fill in the backend's defaults, so they wait until those are loaded.
const ready = ref(false)
const boot = () => run('refresh:', async () => { await loadEnvironment(); ready.value = true })

onMounted(() => bridgeReady().then(boot))
</script>

<template>
  <v-app>
    <v-app-bar flat density="compact" color="background" border="b">
      <v-app-bar-nav-icon aria-label="Show sandboxes" @click="drawer = !drawer" />
      <v-avatar class="mr-3" color="primary" size="28" rounded="lg"><v-icon color="background" size="18">mdi-cube-outline</v-icon></v-avatar>
      <v-app-bar-title class="font-weight-bold ml-0">Microsandbox <span class="text-medium-emphasis font-weight-regular">Studio</span></v-app-bar-title>
      <v-btn class="mr-3" color="primary" variant="tonal" size="small" prepend-icon="mdi-plus" @click="dialog = 'create'">New sandbox</v-btn>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer" temporary width="320" color="surface">
      <div class="d-flex align-center px-4 pt-4 pb-2">
        <span class="text-title-medium font-weight-bold">Sandboxes</span>
        <v-chip size="x-small" variant="tonal" class="ml-2">{{ sandboxes.length }}</v-chip>
        <v-spacer />
        <v-btn icon="mdi-refresh" variant="text" size="small" :loading="busy('refresh', '')" aria-label="Refresh" @click="reload" />
      </div>
      <v-list bg-color="transparent" class="px-2" density="comfortable">
        <v-list-item v-for="s in sandboxes" :key="s.id" :active="selected === s.name" rounded="lg" class="mb-1" @click="select(s.name)">
          <template #prepend><v-avatar color="surface-bright" rounded="lg" size="36"><v-icon size="20">mdi-cube-outline</v-icon></v-avatar></template>
          <v-list-item-title class="font-weight-medium">{{ s.title }}</v-list-item-title>
          <v-list-item-subtitle>{{ s.title !== s.name ? s.name : s.image }}</v-list-item-subtitle>
          <template #append>
            <v-progress-circular v-if="progress[s.name]?.state" v-bind="progressProps(progress[s.name])" class="mr-2" />
            <v-icon :color="statusColor(s.status)" size="10" :aria-label="statusText(s.status)">mdi-circle</v-icon>
            <v-menu location="bottom end">
              <template #activator="{ props }">
                <v-btn v-bind="props" icon="mdi-dots-vertical" variant="text" size="small" class="ml-1" :aria-label="`Actions for ${s.title}`" @click.stop />
              </template>
              <v-list density="compact" min-width="180">
                <v-list-item prepend-icon="mdi-pencil-outline" title="Rename" @click="askRename(s)" />
                <v-list-item prepend-icon="mdi-content-copy" title="Duplicate" :subtitle="s.status === 'running' ? 'Stop it first' : undefined" :disabled="s.status === 'running'" @click="askDuplicate(s)" />
                <v-list-item prepend-icon="mdi-delete-outline" title="Delete" base-color="error" @click="deleteTarget = s" />
              </v-list>
            </v-menu>
          </template>
        </v-list-item>
        <v-list-item v-if="!sandboxes.length" title="No sandboxes yet" subtitle="Create your first environment." />
      </v-list>
      <template #append>
        <div class="pa-4"><v-btn block color="primary" prepend-icon="mdi-plus" @click="dialog = 'create'; drawer = false">New sandbox</v-btn></div>
      </template>
    </v-navigation-drawer>

    <v-main class="d-flex flex-column" style="height: 100vh">
      <div class="flex-grow-1 d-flex flex-column pa-3" style="min-height: 0">
        <v-card v-if="current" rounded="lg" color="surface" border class="flex-grow-1 d-flex flex-column">
          <div class="d-flex align-center ga-2 pl-3 pr-4 py-2">
            <div class="d-flex flex-column mr-2">
              <!-- Disabled buttons get no hover events, so the tooltip hangs on a wrapper. -->
              <v-tooltip v-for="step in [-1, 1]" :key="step" :text="`${step < 0 ? 'Previous' : 'Next'} sandbox (${SHORTCUTS[step]})`" location="bottom">
                <template #activator="{ props }">
                  <span v-bind="props"><v-btn :icon="step < 0 ? 'mdi-chevron-up' : 'mdi-chevron-down'" variant="text" density="compact" size="x-small" :aria-label="`${step < 0 ? 'Previous' : 'Next'} sandbox`" :disabled="!neighbors[step]" @click="select(neighbors[step])" /></span>
                </template>
              </v-tooltip>
            </div>
            <v-icon color="primary">mdi-console</v-icon>
            <span class="text-title-medium font-weight-bold text-truncate">{{ current.title }}</span>
            <v-chip :color="statusColor(current.status)" size="x-small" variant="tonal" prepend-icon="mdi-circle-medium">{{ statusText(current.status) }}</v-chip>
            <v-progress-circular v-if="progress[current.name]?.state" v-bind="progressProps(progress[current.name])" />
            <v-spacer />
            <InstallMenu :disabled="!running" @install="command => terminals[current.name]?.run(command)" />
            <v-tooltip text="Copy files into the sandbox" location="bottom">
              <template #activator="{ props }">
                <v-btn v-bind="props" icon="mdi-upload-outline" variant="text" size="small" aria-label="Copy files into the sandbox" :disabled="!running" @click="dialog = 'copy'" />
              </template>
            </v-tooltip>
            <!-- Disabled buttons get no hover events, so the tooltip hangs on a wrapper. -->
            <v-tooltip :text="running ? 'Stop the sandbox to duplicate it' : 'Duplicate'" location="bottom">
              <template #activator="{ props }">
                <span v-bind="props"><v-btn icon="mdi-content-copy" variant="text" size="small" aria-label="Duplicate" :disabled="running" @click="askDuplicate(current)" /></span>
              </template>
            </v-tooltip>
            <v-tooltip text="Settings" location="bottom">
              <template #activator="{ props }">
                <v-btn v-bind="props" icon="mdi-cog-outline" variant="text" size="small" aria-label="Settings" @click="dialog = 'settings'" />
              </template>
            </v-tooltip>
            <v-btn v-if="running" variant="tonal" size="small" prepend-icon="mdi-stop" :loading="busy('stop')" @click="stop(current.name)">Stop</v-btn>
            <v-btn v-else color="primary" size="small" prepend-icon="mdi-play" :loading="busy('start')" @click="start(current.name)">Start</v-btn>
          </div>
          <v-divider />
          <div class="flex-grow-1 position-relative">
            <TerminalCard
              v-for="s in opened" v-show="s.name === selected" :key="s.id"
              :ref="card => card ? terminals[s.name] = card : delete terminals[s.name]"
              :sandbox="s.name" :running="s.status === 'running'" :active="s.name === selected" @error="fail" @progress="p => progress[s.name] = p"
            />
            <v-overlay :model-value="!running" contained persistent no-click-animation class="align-center justify-center" scrim="#090F1C" opacity="0.85">
              <v-card rounded="xl" color="surface" border class="text-center pa-6" max-width="380">
                <v-avatar size="56" rounded="xl" color="surface-bright" class="mb-4"><v-icon size="30" color="primary">mdi-power</v-icon></v-avatar>
                <div class="text-title-large font-weight-bold mb-1">Sandbox is stopped</div>
                <p class="text-body-medium text-medium-emphasis mb-5">The shell connects automatically when it starts.</p>
                <v-btn color="primary" prepend-icon="mdi-play" :loading="busy('start')" @click="start(current.name)">Start</v-btn>
              </v-card>
            </v-overlay>
          </div>
        </v-card>

        <div v-else-if="loaded" class="flex-grow-1 d-flex align-center justify-center">
          <v-card rounded="xl" color="surface" border max-width="460" class="text-center pa-8">
            <v-avatar size="80" rounded="xl" color="surface-bright" class="mb-5"><v-icon size="42" color="primary">mdi-cube-outline</v-icon></v-avatar>
            <h1 class="text-headline-small font-weight-bold mb-2">No sandboxes yet</h1>
            <p class="text-body-large text-medium-emphasis mb-6">Spin up a new sandbox. The shell connects automatically afterwards.</p>
            <v-btn color="primary" size="large" prepend-icon="mdi-plus" @click="dialog = 'create'">Create sandbox</v-btn>
          </v-card>
        </div>
      </div>
    </v-main>

    <v-snackbar v-model="toast.show" :color="toast.color" :timeout="toast.color === 'error' ? -1 : 5000" location="bottom right" multi-line>
      {{ toast.text }}
      <template #actions><v-btn icon="mdi-close" variant="text" size="small" aria-label="Close" @click="toast.show = false" /></template>
    </v-snackbar>

    <CreateDialog v-if="ready" v-model="createOpen" @created="created" />
    <SettingsDialog v-if="ready && current" v-model="settingsOpen" :sandbox="current" @saved="saved" @recreated="reload" @rename="askRename(current)" @delete="deleteTarget = current" />
    <CopyDialog v-if="current" v-model="copyOpen" :sandbox="current.name" />

    <v-dialog v-model="renameOpen" max-width="420">
      <v-card rounded="xl" color="surface">
        <v-card-title class="px-6 pt-6">Rename sandbox</v-card-title>
        <v-card-text class="px-6">
          <v-text-field v-model="renameText" label="Display name" variant="outlined" autofocus :placeholder="renameTarget?.name" hint="Leave empty to show the technical name. The CLI and SDK keep using the technical name." persistent-hint @keyup.enter="rename" />
        </v-card-text>
        <v-card-actions class="px-6 pb-6">
          <v-spacer />
          <v-btn variant="text" @click="renameTarget = null">Cancel</v-btn>
          <v-btn color="primary" :loading="busy('rename', '')" @click="rename">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="duplicateOpen" max-width="420" :persistent="busy('duplicate', '')">
      <v-card rounded="xl" color="surface">
        <v-card-title class="px-6 pt-6">Duplicate sandbox</v-card-title>
        <v-card-text class="px-6">
          <v-text-field v-model="duplicateText" label="Name of the copy" variant="outlined" autofocus :disabled="busy('duplicate', '')" hint="The copy gets the files of the sandbox. Workspace folders stay the same host folders." persistent-hint @keyup.enter="duplicate" />
        </v-card-text>
        <v-card-actions class="px-6 pb-6">
          <v-spacer />
          <v-btn variant="text" :disabled="busy('duplicate', '')" @click="duplicateTarget = null">Cancel</v-btn>
          <v-btn color="primary" :loading="busy('duplicate', '')" @click="duplicate">Duplicate</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="deleteOpen" max-width="420">
      <v-card rounded="xl" color="surface">
        <v-card-title class="px-6 pt-6">Delete sandbox?</v-card-title>
        <v-card-text class="px-6">{{ deleteTarget?.title }} and its data will be removed permanently.</v-card-text>
        <v-card-actions class="px-6 pb-6">
          <v-spacer />
          <v-btn variant="text" @click="deleteTarget = null">Cancel</v-btn>
          <v-btn color="error" :loading="busy('delete', '')" @click="remove">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="closeOpen" max-width="460" :persistent="busy('quit', 'stop')">
      <v-card rounded="xl" color="surface">
        <v-card-title class="px-6 pt-6">{{ closeRunning.length === 1 ? 'A sandbox is still running' : `${closeRunning.length} sandboxes are still running` }}</v-card-title>
        <v-card-text class="px-6">
          <p class="mb-3">{{ closeTitles.join(', ') }} {{ closeRunning.length === 1 ? 'keeps' : 'keep' }} running after the app closes. Shells and running programs carry on; next time you open the app you can pick up where you left off.</p>
          <p class="text-medium-emphasis">Stopping ends the shells and every program running in them.</p>
        </v-card-text>
        <v-card-actions class="px-6 pb-6 flex-wrap">
          <v-btn variant="text" :disabled="busy('quit', 'stop')" @click="closeRunning = []">Cancel</v-btn>
          <v-spacer />
          <v-btn variant="tonal" prepend-icon="mdi-stop" :loading="busy('quit', 'stop')" :disabled="busy('quit', '')" @click="quit(true)">Stop all & close</v-btn>
          <v-btn color="primary" :loading="busy('quit', '')" :disabled="busy('quit', 'stop')" @click="quit()">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app>
</template>
