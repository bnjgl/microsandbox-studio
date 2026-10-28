<script setup>
import { computed, ref } from 'vue'
import { api } from '../bridge'
import { useTask } from '../composables'
import { CPU_CHOICES, MEMORY_CHOICES, MODES, defaultNetwork, emptyRows, environmentSummary, fromRows, networkSummary, newPort, once, portNumber, required, sandboxName, workspaceSummary } from '../sandbox'
import EnvironmentForm from './EnvironmentForm.vue'
import WorkspaceFolders from './WorkspaceFolders.vue'

const open = defineModel({ type: Boolean })
const emit = defineEmits(['created'])

const defaults = () => ({
  name: '', image: 'mcr.microsoft.com/devcontainers/base:ubuntu-24.04', cpus: 1, memory: 1024,
  folders: [], environment: emptyRows(), network: defaultNetwork(),
})
const form = ref(defaults()), formRef = ref(null)
const { busy: creating, error, run } = useTask()
const variables = computed(() => fromRows(form.value.environment))
const hostPorts = computed(() => form.value.network.ports.map(port => port.host))
const counts = computed(() => ({ variables: Object.keys(variables.value.env).length, secrets: Object.keys(variables.value.secrets).length }))

async function create() {
  if (!(await formRef.value.validate()).valid) { error.value = 'Check the marked fields.'; return }
  return run(async () => {
    const { name, image, cpus, memory, folders, network } = form.value
    await api().create_sandbox({
      name: name.trim(), image: image.trim(), cpus, memory, folders: folders.map(folder => folder.source),
      environment: variables.value, network,
    })
    emit('created', name.trim())
    form.value = defaults()
    open.value = false
  })
}
</script>

<template>
  <v-dialog v-model="open" max-width="720" scrollable :persistent="creating">
    <v-card color="surface">
      <v-card-title class="px-6 pt-6 text-title-large font-pixel">New sandbox</v-card-title>
      <v-card-text class="px-6 pt-4">
        <v-form ref="formRef" validate-on="blur">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4 text-pre-wrap">{{ error }}</v-alert>
        <v-text-field v-model="form.name" label="Name" placeholder="devbox" variant="outlined" :rules="[sandboxName]" autofocus class="mb-2" :disabled="creating" />
        <v-text-field v-model="form.image" label="Container image" variant="outlined" :rules="[required]" class="mb-2" :disabled="creating" />
        <v-row>
          <v-col cols="6"><v-select v-model="form.cpus" label="CPUs" :items="CPU_CHOICES" variant="outlined" :disabled="creating" /></v-col>
          <v-col cols="6"><v-select v-model="form.memory" label="Memory (MiB)" :items="MEMORY_CHOICES" variant="outlined" :disabled="creating" /></v-col>
        </v-row>

        <v-expansion-panels variant="accordion" multiple>
          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon class="mr-3" color="primary">mdi-key-variant</v-icon>Variables &amp; secrets
              <v-spacer /><span class="text-body-small text-medium-emphasis mr-2">{{ environmentSummary(counts) }}</span>
            </v-expansion-panel-title>
            <v-expansion-panel-text><EnvironmentForm v-model="form.environment" :disabled="creating" /></v-expansion-panel-text>
          </v-expansion-panel>

          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon class="mr-3" color="primary">mdi-lan</v-icon>Network
              <v-spacer /><span class="text-body-small text-medium-emphasis mr-2">{{ networkSummary(form.network) }}</span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-radio-group v-model="form.network.mode" hide-details :disabled="creating">
                <v-radio v-for="mode in MODES" :key="mode.value" :value="mode.value" color="primary">
                  <template #label><div><div>{{ mode.title }}</div><div class="text-body-small text-medium-emphasis">{{ mode.text }}</div></div></template>
                </v-radio>
              </v-radio-group>
              <div class="d-flex align-center justify-space-between mt-5 mb-1">
                <span class="text-title-small font-weight-bold">Ports</span>
                <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="creating" @click="form.network.ports.push(newPort())">Port</v-btn>
              </div>
              <p class="text-body-small text-medium-emphasis mb-3">Makes a service in the sandbox reachable on this computer, e.g. localhost:8080 → sandbox port 80.</p>
              <v-row v-for="(port, index) in form.network.ports" :key="index" dense align="center">
                <v-col cols="5"><v-text-field v-model.number="port.host" type="number" label="Host port" placeholder="8080" variant="outlined" density="compact" hide-details="auto" :rules="[portNumber, once(hostPorts, 'Already used')]" :disabled="creating" /></v-col>
                <v-col cols="6"><v-text-field v-model.number="port.guest" type="number" label="Sandbox port" placeholder="80" variant="outlined" density="compact" hide-details="auto" :rules="[portNumber]" :disabled="creating" /></v-col>
                <v-col cols="1" class="text-right"><v-btn icon="mdi-close" size="small" variant="text" aria-label="Remove port" :disabled="creating" @click="form.network.ports.splice(index, 1)" /></v-col>
              </v-row>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon class="mr-3" color="primary">mdi-folder-multiple-outline</v-icon>Workspace folders
              <v-spacer /><span class="text-body-small text-medium-emphasis mr-2">{{ workspaceSummary(form.folders) }}</span>
            </v-expansion-panel-title>
            <v-expansion-panel-text><WorkspaceFolders v-model="form.folders" :disabled="creating" /></v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <p class="text-body-small text-medium-emphasis mt-3">Network and workspace folders cannot be changed later.</p>
        </v-form>
      </v-card-text>
      <v-card-actions class="px-6 pb-6">
        <v-spacer />
        <v-btn variant="text" :disabled="creating" @click="open = false">Cancel</v-btn>
        <v-btn color="primary" :loading="creating" @click="create">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
