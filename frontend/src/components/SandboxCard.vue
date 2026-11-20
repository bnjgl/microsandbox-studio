<script setup>
import { computed, ref } from 'vue'
import { api } from '../bridge'
import { environmentSummary, modeDescription, networkSummary, resourcesSummary, snapshotDate, snapshotSummary, statusColor, statusText, workspaceSummary } from '../sandbox'
import EnvironmentEditor from './EnvironmentEditor.vue'
import ResourcesEditor from './ResourcesEditor.vue'
import SshPanel from './SshPanel.vue'

const props = defineProps({ sandbox: { type: Object, required: true }, ssh: { type: Object, required: true } })
const emit = defineEmits(['changed', 'notify', 'restore'])

const { name } = props.sandbox
const dialog = ref('')
const busy = ref('')
const removing = ref(null)
const unfolded = ref({ network: false, folders: false, snapshots: false })
const running = computed(() => props.sandbox.status === 'running')
const dialogOpen = computed({ get: () => !!dialog.value, set: open => { if (!open) dialog.value = '' } })
const DIALOG_TITLES = { resources: 'Resources', environment: 'Variables & secrets' }

const CONFIRM = {
  stop: {
    title: 'Stop', text: 'Programs in the sandbox end and SSH connections drop. Files stay.', color: 'primary',
    run: () => api().stop_sandbox(name), done: `${name} stopped.`,
  },
  delete: {
    title: 'Delete', text: 'The sandbox, its data and its snapshots are removed permanently. Mounted host folders are kept.', color: 'error',
    run: () => api().delete_sandbox(name), done: `${name} deleted.`,
  },
  snapshot: {
    title: 'Delete', question: 'Delete this snapshot?', text: 'The snapshot is removed permanently. Sandboxes restored from it are kept.', color: 'error',
    run: () => api().delete_snapshot(name, removing.value.reference), done: 'Snapshot deleted.',
  },
}
const menu = computed(() => [
  ...(running.value ? [{ title: 'Stop', icon: 'mdi-stop', dialog: 'stop' }] : []),
  { title: 'Delete', icon: 'mdi-delete-outline', dialog: 'delete', color: 'error' },
])

async function act(action, task) {
  busy.value = action
  try { const message = await task(); if (message) emit('notify', message) } catch (e) { emit('notify', String(e), 'error') }
  finally { busy.value = ''; emit('changed') }
}
const start = () => act('start', () => api().start_sandbox(name))
const takeSnapshot = () => act('take', async () => { await api().take_snapshot(name); return 'Snapshot taken.' })
const confirmed = action => act(action, async () => {
  await CONFIRM[action].run()
  dialog.value = ''
  return CONFIRM[action].done
})
const sshText = computed(() => {
  if (!props.sandbox.host) return 'This name cannot be used as an SSH host'
  if (!props.ssh.on) return 'Turn on Use SSH in the top bar first'
  if (!props.ssh.included) return 'Add the Include line to your SSH config first'
  return running.value ? 'For a terminal, an editor or an agent' : props.sandbox.host
})

function saved(message) { dialog.value = ''; emit('notify', message); emit('changed') }
</script>

<template>
  <v-card color="surface" border class="h-100 d-flex flex-column">
    <v-card-item class="pt-4">
      <v-card-title class="font-pixel text-truncate">{{ sandbox.name }}</v-card-title>
      <v-card-subtitle class="text-truncate" @mouseenter="e => e.target.title = e.target.scrollWidth > e.target.clientWidth ? sandbox.image : ''">{{ sandbox.image }}</v-card-subtitle>
      <template #append>
        <v-chip :color="statusColor(sandbox.status)" size="x-small" variant="tonal" prepend-icon="mdi-circle-medium" class="mr-1">{{ statusText(sandbox.status) }}</v-chip>
        <v-menu location="bottom end">
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" icon="mdi-dots-vertical" variant="text" size="small" :loading="busy === 'stop' || busy === 'delete'" :disabled="!!busy" :aria-label="`Actions for ${sandbox.name}`" />
          </template>
          <v-list density="compact" min-width="160">
            <v-list-item v-for="item in menu" :key="item.dialog" :prepend-icon="item.icon" :title="item.title" :base-color="item.color" @click="dialog = item.dialog" />
          </v-list>
        </v-menu>
      </template>
    </v-card-item>
    <v-divider />

    <div v-if="sandbox.problem" class="flex-grow-1 pa-4">
      <v-alert type="warning" variant="tonal" density="compact">{{ sandbox.problem }}</v-alert>
    </div>

    <v-list v-else bg-color="transparent" density="comfortable" class="flex-grow-1 py-1">
      <div v-if="!running" class="px-4 pt-2 pb-3">
        <v-btn block color="primary" prepend-icon="mdi-play" :loading="busy === 'start'" :disabled="!!busy" @click="start">Start</v-btn>
      </div>
      <v-list-item prepend-icon="mdi-ssh" title="SSH" :subtitle="sshText" />
      <SshPanel v-if="running && ssh.on && ssh.included && sandbox.host" :sandbox="sandbox" @notify="(...args) => emit('notify', ...args)" />
      <v-divider class="my-1" />

      <v-list-item prepend-icon="mdi-chip" title="Resources" @click="dialog = 'resources'">
        <template #append><v-chip size="small" variant="tonal" color="primary">{{ resourcesSummary(sandbox) }}</v-chip></template>
      </v-list-item>
      <v-list-item prepend-icon="mdi-key-variant" title="Variables & secrets" @click="dialog = 'environment'">
        <template #append><v-chip size="small" variant="tonal" color="primary">{{ environmentSummary(sandbox.environment) }}</v-chip></template>
      </v-list-item>

      <v-list-item prepend-icon="mdi-lan" title="Network" @click="unfolded.network = !unfolded.network">
        <template #append>
          <v-chip size="small" variant="tonal">{{ networkSummary(sandbox.network) }}</v-chip>
          <v-icon class="ml-1" size="20">{{ unfolded.network ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </template>
      </v-list-item>
      <v-expand-transition>
        <div v-if="unfolded.network" class="px-4 pb-3 text-body-small">
          <p class="text-medium-emphasis mb-2">{{ modeDescription(sandbox.network.mode) }}</p>
          <div v-for="port in sandbox.network.ports" :key="port.host" class="font-monospace">localhost:{{ port.host }} → {{ port.guest }}</div>
          <p v-if="!sandbox.network.ports.length" class="text-medium-emphasis">No ports mapped.</p>
        </div>
      </v-expand-transition>

      <v-list-item prepend-icon="mdi-folder-multiple-outline" title="Workspace folders" @click="unfolded.folders = !unfolded.folders">
        <template #append>
          <v-chip size="small" variant="tonal">{{ workspaceSummary(sandbox.folders) }}</v-chip>
          <v-icon class="ml-1" size="20">{{ unfolded.folders ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </template>
      </v-list-item>
      <v-expand-transition>
        <div v-if="unfolded.folders" class="px-4 pb-3 text-body-small">
          <div v-for="folder in sandbox.folders" :key="folder.target" class="mb-2 text-break">
            <div>{{ folder.source }}</div>
            <div class="text-medium-emphasis font-monospace">→ {{ folder.target }}</div>
          </div>
          <p v-if="!sandbox.folders.length" class="text-medium-emphasis">No folders mounted.</p>
        </div>
      </v-expand-transition>

      <v-list-item prepend-icon="mdi-camera-outline" title="Snapshots" @click="unfolded.snapshots = !unfolded.snapshots">
        <template #append>
          <v-chip size="small" variant="tonal">{{ snapshotSummary(sandbox.snapshots) }}</v-chip>
          <v-icon class="ml-1" size="20">{{ unfolded.snapshots ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
        </template>
      </v-list-item>
      <v-expand-transition>
        <div v-if="unfolded.snapshots" class="px-4 pb-3 text-body-small">
          <v-btn block variant="tonal" size="small" prepend-icon="mdi-camera-plus-outline" class="mb-2" :loading="busy === 'take'" :disabled="!!busy" @click="takeSnapshot">Take snapshot</v-btn>
          <div v-for="snapshot in sandbox.snapshots" :key="snapshot.reference" class="d-flex align-center ga-1">
            <div class="flex-grow-1 text-break">
              <div>{{ snapshotDate(snapshot.created) }}</div>
              <div class="text-medium-emphasis font-monospace">{{ snapshot.name }}</div>
            </div>
            <v-btn icon="mdi-backup-restore" size="small" variant="text" title="New sandbox from this snapshot" aria-label="New sandbox from this snapshot" :disabled="!!busy" @click="emit('restore', { sandbox, snapshot })" />
            <v-btn icon="mdi-delete-outline" size="small" variant="text" color="error" title="Delete snapshot" aria-label="Delete snapshot" :disabled="!!busy" @click="removing = snapshot; dialog = 'snapshot'" />
          </div>
          <p v-if="!sandbox.snapshots.length" class="text-medium-emphasis">No snapshots yet.</p>
        </div>
      </v-expand-transition>
    </v-list>
  </v-card>

  <v-dialog v-model="dialogOpen" :max-width="CONFIRM[dialog] ? 420 : 760" scrollable :persistent="busy === dialog">
    <v-card v-if="CONFIRM[dialog]" color="surface">
      <v-card-title class="px-6 pt-6 font-pixel">{{ CONFIRM[dialog].question ?? `${CONFIRM[dialog].title} ${sandbox.name}?` }}</v-card-title>
      <v-card-text class="px-6">{{ CONFIRM[dialog].text }}</v-card-text>
      <v-card-actions class="px-6 pb-6">
        <v-spacer />
        <v-btn variant="text" :disabled="busy === dialog" @click="dialog = ''">Cancel</v-btn>
        <v-btn :color="CONFIRM[dialog].color" variant="flat" :loading="busy === dialog" @click="confirmed(dialog)">{{ CONFIRM[dialog].title }}</v-btn>
      </v-card-actions>
    </v-card>
    <v-card v-else-if="dialog" color="surface">
      <v-card-item class="px-6 pt-5">
        <v-card-title class="font-pixel">{{ DIALOG_TITLES[dialog] }}</v-card-title>
        <v-card-subtitle>{{ sandbox.name }}</v-card-subtitle>
      </v-card-item>
      <v-divider />
      <ResourcesEditor v-if="dialog === 'resources'" :sandbox="sandbox" @saved="saved" @cancel="dialog = ''" />
      <EnvironmentEditor v-else-if="dialog === 'environment'" :sandbox="sandbox" @saved="saved" @cancel="dialog = ''" />
    </v-card>
  </v-dialog>
</template>
