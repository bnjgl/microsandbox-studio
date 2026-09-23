<script setup>
import { computed, ref, watch } from 'vue'
import { api, track } from '../api'

const open = defineModel({ type: Boolean })
const props = defineProps({ sandbox: { type: String, required: true } })

const paths = ref([]), destination = ref('/uploads'), result = ref(null), error = ref('')
const picking = ref(false), copying = ref(false)
const busy = computed(() => picking.value || copying.value)

watch(open, isOpen => {
  if (isOpen) { paths.value = []; destination.value = '/uploads'; result.value = null; error.value = '' }
})

function addSources(folders) {
  result.value = null
  return track(picking, error, async () => {
    paths.value = [...new Set([...paths.value, ...await api().select_copy_sources(folders)])]
  })
}

function copy() {
  result.value = null
  return track(copying, error, async () => {
    result.value = await api().copy_into_sandbox(props.sandbox, [...paths.value], destination.value)
    paths.value = []
  })
}
</script>

<template>
  <v-dialog v-model="open" max-width="680" :persistent="busy" scrollable>
    <v-card rounded="xl" color="surface">
      <v-card-title class="px-6 pt-6">Copy files into {{ sandbox }}</v-card-title>
      <v-card-text class="px-6 pt-4">
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-alert v-if="result" :type="result.skipped ? 'info' : 'success'" variant="tonal" class="mb-4">
          Copied {{ result.files }} files and {{ result.directories }} folders.
          <span v-if="result.skipped">Skipped {{ result.skipped }} symbolic links or special files.</span>
        </v-alert>
        <v-text-field v-model="destination" label="Destination folder in the sandbox" placeholder="/uploads" variant="outlined" :disabled="busy" hint="Created if needed. Existing targets with the same name are not overwritten." persistent-hint class="mb-4" />
        <div class="d-flex flex-wrap ga-2 mb-4">
          <v-btn variant="tonal" prepend-icon="mdi-file-plus-outline" :disabled="busy" @click="addSources(false)">Select files</v-btn>
          <v-btn variant="tonal" prepend-icon="mdi-folder-plus-outline" :disabled="busy" @click="addSources(true)">Select folders</v-btn>
        </div>
        <p class="text-body-medium text-medium-emphasis mb-3">Folders are copied with subfolders and hidden files. Symbolic links and special files are skipped.</p>
        <v-card v-for="(path, index) in paths" :key="path" variant="outlined" class="mb-2">
          <v-card-text class="d-flex align-center ga-3 py-2">
            <span class="flex-grow-1 text-body-medium text-break">{{ path }}</span>
            <v-btn icon="mdi-close" size="small" variant="text" :aria-label="`Remove ${path}`" :disabled="busy" @click="paths.splice(index, 1)" />
          </v-card-text>
        </v-card>
        <v-progress-linear v-if="busy" indeterminate color="primary" class="mt-4" />
        <p v-if="copying" class="text-body-small text-medium-emphasis mt-2">Copying to {{ destination }} …</p>
      </v-card-text>
      <v-card-actions class="px-6 pb-6">
        <v-spacer />
        <v-btn variant="text" :disabled="busy" @click="open = false">Close</v-btn>
        <v-btn color="primary" :loading="copying" :disabled="busy || !paths.length || !destination.startsWith('/')" @click="copy">Copy</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
