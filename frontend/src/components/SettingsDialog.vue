<script setup>
// Settings for one sandbox: an overview of all areas, each opens its own page.
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import { summary as environmentSummary } from '../environment'
import { networkSummary } from '../network'
import { statusText } from '../status'
import { workspaceSummary } from '../workspaces'
import EnvironmentEditor from './EnvironmentEditor.vue'
import NetworkEditor from './NetworkEditor.vue'
import WorkspaceEditor from './WorkspaceEditor.vue'

const open = defineModel({ type: Boolean })
const props = defineProps({ sandbox: { type: Object, required: true } })
const emit = defineEmits(['saved', 'recreated', 'rename', 'delete'])

const page = ref('overview') // 'overview' | 'general' | 'environment' | 'network' | 'workspaces'
const summary = ref(null), network = ref(null), folders = ref(null), busy = ref(false)
const terminalCommand = ref(''), terminalCopied = ref(false)

const dateText = v => v ? new Date(v * 1000).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
const renamed = computed(() => props.sandbox.title !== props.sandbox.name)

const sections = computed(() => [
  { page: 'general', icon: 'mdi-card-text-outline', title: 'General', text: 'Name, image and status of the sandbox.', chip: statusText(props.sandbox.status) },
  { page: 'environment', icon: 'mdi-key-variant', title: 'Variables & secrets', text: 'Environment variables and protected credentials for programs in the sandbox.', chip: summary.value ?? '…' },
  { page: 'network', icon: 'mdi-lan', title: 'Network', text: 'Internet access, custom rules and port mappings.', chip: network.value ?? '…' },
  { page: 'workspaces', icon: 'mdi-folder-multiple-outline', title: 'Workspace folders', text: 'Local folders mounted under /workspaces.', chip: folders.value ?? '…' },
])
const title = computed(() => ({ general: 'General', environment: 'Variables & secrets', network: 'Network', workspaces: 'Workspace folders' })[page.value] || 'Settings')

// Shows `fallback(error)` in `target` when loading fails; `empty` while loading.
async function load(target, task, fallback, empty = null) {
  target.value = empty
  try { target.value = await task() } catch (e) { target.value = fallback(e) }
}

async function loadSummary() {
  const { name } = props.sandbox
  await load(summary, async () => environmentSummary((await api().get_environment(name)).settings), () => 'Unreadable')
  await load(network, async () => networkSummary((await api().get_network(name)).settings), () => 'Unreadable')
  await load(folders, async () => workspaceSummary((await api().get_workspaces(name)).folders), () => 'Unreadable')
}

function loadTerminalCommand() {
  terminalCopied.value = false
  return load(terminalCommand, () => api().terminal_command(props.sandbox.name), e => `Not available: ${e}`, '')
}

watch(open, isOpen => { if (isOpen) { page.value = 'overview'; loadSummary(); loadTerminalCommand() } })
async function copyTerminalCommand() {
  try { await api().copy_to_clipboard(terminalCommand.value); terminalCopied.value = true }
  catch (e) { terminalCommand.value = `Kopieren fehlgeschlagen: ${e}` }
}

function saved(message, result) {
  emit('saved', message, result)
  page.value = 'overview'
  loadSummary()
}
</script>

<template>
  <v-dialog v-model="open" max-width="880" scrollable>
    <v-card rounded="xl" color="surface">
      <v-card-item class="px-6 pt-5 pb-3">
        <template #prepend>
          <v-btn v-if="page !== 'overview'" icon="mdi-arrow-left" variant="text" class="mr-1" aria-label="Back to overview" :disabled="busy" @click="page = 'overview'" />
          <v-avatar v-else color="surface-bright" rounded="lg" class="mr-2"><v-icon color="primary">mdi-cog-outline</v-icon></v-avatar>
        </template>
        <v-card-title class="font-weight-bold">{{ title }}</v-card-title>
        <v-card-subtitle>{{ sandbox.title }}</v-card-subtitle>
        <template #append>
          <v-btn icon="mdi-close" variant="text" aria-label="Close" @click="open = false" />
        </template>
      </v-card-item>
      <v-divider />

      <v-card-text v-if="page === 'overview'" class="px-6 py-5">
        <v-row>
          <v-col v-for="section in sections" :key="section.page" cols="12" sm="6">
            <v-card color="surface-bright" variant="flat" rounded="lg" class="h-100" @click="page = section.page">
              <v-card-item>
                <template #prepend><v-avatar color="background" rounded="lg"><v-icon color="primary">{{ section.icon }}</v-icon></v-avatar></template>
                <v-card-title class="text-title-medium font-weight-bold">{{ section.title }}</v-card-title>
                <template #append><v-icon color="medium-emphasis">mdi-chevron-right</v-icon></template>
              </v-card-item>
              <v-card-text>
                <p class="text-body-medium text-medium-emphasis mb-3">{{ section.text }}</p>
                <v-chip size="small" variant="tonal" color="primary">{{ section.chip }}</v-chip>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-card variant="outlined" color="secondary" rounded="lg" class="mt-6">
          <v-card-item>
            <template #prepend><v-icon>mdi-console-line</v-icon></template>
            <v-card-title class="text-title-medium font-weight-bold">Connect from a terminal</v-card-title>
          </v-card-item>
          <v-card-text>
            <v-text-field
              :model-value="terminalCommand" readonly variant="outlined" base-color="secondary" color="secondary" density="compact" hide-details class="font-monospace" :loading="!terminalCommand"
              :append-inner-icon="terminalCopied ? 'mdi-check' : 'mdi-content-copy'" aria-label="Command for your own terminal" @click:append-inner="copyTerminalCommand"
            />
          </v-card-text>
        </v-card>

        <div class="text-label-medium text-uppercase text-medium-emphasis mt-6 mb-2">Danger zone</div>
        <v-card variant="outlined" color="error" rounded="lg">
          <v-card-item>
            <template #prepend><v-icon color="error">mdi-delete-outline</v-icon></template>
            <v-card-title class="text-title-medium font-weight-bold">Delete sandbox</v-card-title>
            <v-card-subtitle>Permanently removes the sandbox and its data. Mounted host folders are kept.</v-card-subtitle>
            <template #append><v-btn color="error" variant="tonal" @click="emit('delete')">Delete</v-btn></template>
          </v-card-item>
        </v-card>
      </v-card-text>

      <v-card-text v-else-if="page === 'general'" class="px-6 py-5">
        <v-list bg-color="transparent" lines="two" class="pa-0">
          <v-list-item title="Display name" :subtitle="sandbox.title" prepend-icon="mdi-rename-outline">
            <template #append><v-btn variant="tonal" size="small" prepend-icon="mdi-pencil-outline" @click="emit('rename')">Rename</v-btn></template>
          </v-list-item>
          <v-list-item title="Technical name" :subtitle="sandbox.name" prepend-icon="mdi-identifier" />
          <v-list-item title="Container image" :subtitle="sandbox.image" prepend-icon="mdi-layers-outline" />
          <v-list-item title="Status" :subtitle="statusText(sandbox.status)" prepend-icon="mdi-pulse" />
          <v-list-item title="Created" :subtitle="dateText(sandbox.created_at)" prepend-icon="mdi-calendar-outline" />
        </v-list>
        <p class="text-body-small text-medium-emphasis mt-3">
          The display name only applies in this app. The CLI and SDK keep using the technical name{{ renamed ? ` “${sandbox.name}”` : '' }}.
        </p>
      </v-card-text>

      <EnvironmentEditor v-else-if="page === 'environment'" :sandbox="sandbox.name" @saved="saved" @cancel="page = 'overview'" @busy="value => busy = value" />

      <NetworkEditor v-else-if="page === 'network'" :sandbox="sandbox.name" @saved="saved" @recreated="emit('recreated')" @cancel="page = 'overview'" @busy="value => busy = value" />

      <WorkspaceEditor v-else-if="page === 'workspaces'" :sandbox="sandbox.name" @saved="saved" @recreated="emit('recreated')" @cancel="page = 'overview'" @busy="value => busy = value" />
    </v-card>
  </v-dialog>
</template>
