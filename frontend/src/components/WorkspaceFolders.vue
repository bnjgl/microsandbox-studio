<script setup>
import { api } from '../bridge'
import { useTask } from '../composables'

const folders = defineModel({ type: Array, required: true })
defineProps({ disabled: Boolean })

const { busy: picking, error, run } = useTask()

function pickFolders() {
  return run(async () => {
    folders.value = await api().select_workspace_folders(folders.value.map(folder => folder.source))
  })
}
</script>

<template>
  <div class="d-flex align-center justify-space-between ga-3 mb-2">
    <span class="text-title-medium font-weight-bold">Workspace folders</span>
    <v-btn variant="tonal" size="small" prepend-icon="mdi-folder-plus-outline" :loading="picking" :disabled="disabled" @click="pickFolders">Add folders</v-btn>
  </div>
  <p class="text-body-medium text-medium-emphasis mb-3">Optional: choose one or more local folders. Changes in the sandbox are saved directly in the local folder.</p>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-3">{{ error }}</v-alert>
  <v-card v-for="(folder, index) in folders" :key="folder.source" variant="outlined" class="mb-2">
    <v-card-text class="d-flex align-center ga-3 py-3">
      <v-icon color="primary">mdi-folder-outline</v-icon>
      <div class="flex-grow-1 text-break">
        <div class="text-body-medium">{{ folder.source }}</div>
        <div class="text-body-small text-medium-emphasis">→ {{ folder.target }}</div>
      </div>
      <v-btn icon="mdi-close" size="small" variant="text" :aria-label="`Remove ${folder.source}`" :disabled="disabled || picking" @click="folders = folders.toSpliced(index, 1)" />
    </v-card-text>
  </v-card>
  <p v-if="folders.length" class="text-body-small text-medium-emphasis mt-2">Programs start in the first workspace folder.</p>
</template>
