<script setup>
import { computed, ref } from 'vue'
import { api, track, useEnvironment } from '../api'
import { summary as environmentSummary } from '../environment'
import { defaultNetwork, networkSummary } from '../network'
import EnvironmentDialog from './EnvironmentDialog.vue'
import NetworkDialog from './NetworkDialog.vue'
import WorkspaceFolders from './WorkspaceFolders.vue'

const open = defineModel({ type: Boolean })
const emit = defineEmits(['created'])

const { emptySettings } = useEnvironment()
const defaults = () => ({ name: '', image: 'mcr.microsoft.com/devcontainers/base:ubuntu-24.04', memory: 1024, cpus: 1, folders: [], settings: emptySettings(), network: defaultNetwork() })
const form = ref(defaults())
const creating = ref(false), picking = ref(false), error = ref(''), environmentOpen = ref(false), networkOpen = ref(false)
const busy = computed(() => creating.value || picking.value)

function create() {
  return track(creating, error, async () => {
    const { name, image, memory, cpus, folders, settings, network } = form.value
    await api().create_sandbox(name, image, memory, cpus, folders, settings, network)
    emit('created', name.trim())
    form.value = defaults()
    open.value = false
  })
}
</script>

<template>
  <v-dialog v-model="open" max-width="680" :persistent="busy">
    <v-card rounded="xl" color="surface">
      <v-card-title class="px-6 pt-6 text-title-large">New sandbox</v-card-title>
      <v-card-subtitle class="px-6">Configure your local environment.</v-card-subtitle>
      <v-card-text class="px-6 pt-6">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-text-field v-model="form.name" label="Name" placeholder="devbox" variant="outlined" autofocus class="mb-2" :disabled="creating" />
        <v-text-field v-model="form.image" label="Container image" variant="outlined" class="mb-2" :disabled="creating" />
        <v-row>
          <v-col cols="6"><v-select v-model="form.cpus" label="CPUs" :items="[1, 2, 4, 8]" variant="outlined" :disabled="creating" /></v-col>
          <v-col cols="6"><v-select v-model="form.memory" label="Memory (MiB)" :items="[512, 1024, 2048, 4096, 8192]" variant="outlined" :disabled="creating" /></v-col>
        </v-row>
        <div class="d-flex align-center flex-wrap ga-3 mb-5">
          <v-btn variant="tonal" prepend-icon="mdi-tune-variant" :disabled="creating" @click="environmentOpen = true">Variables &amp; secrets</v-btn>
          <span class="text-body-small text-medium-emphasis">{{ environmentSummary(form.settings) }}</span>
        </div>
        <div class="d-flex align-center flex-wrap ga-3 mb-5">
          <v-btn variant="tonal" prepend-icon="mdi-lan" :disabled="creating" @click="networkOpen = true">Network</v-btn>
          <span class="text-body-small text-medium-emphasis">{{ networkSummary(form.network) }}</span>
        </div>
        <WorkspaceFolders v-model="form.folders" :disabled="creating" @busy="value => picking = value" />
      </v-card-text>
      <v-card-actions class="px-6 pb-6">
        <v-spacer />
        <v-btn variant="text" :disabled="busy" @click="open = false">Cancel</v-btn>
        <v-btn color="primary" :loading="creating" :disabled="picking" @click="create">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <EnvironmentDialog v-model="environmentOpen" :initial="form.settings" @apply="settings => form.settings = settings" />
  <NetworkDialog v-model="networkOpen" :initial="form.network" @apply="network => form.network = network" />
</template>
