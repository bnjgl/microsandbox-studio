<script setup>
import { useCopy } from '../composables'

defineProps({ sandbox: { type: Object, required: true } })
const emit = defineEmits(['notify'])

const { copy: copyToClipboard, copyIcon } = useCopy()

async function copy(text) {
  try { await copyToClipboard(text) } catch (e) { emit('notify', String(e), 'error') }
}
</script>

<template>
  <div class="d-flex flex-column ga-3 px-4 pt-3 pb-3">
    <v-text-field
      :model-value="sandbox.host" label="SSH host" readonly variant="outlined" density="compact" hide-details class="font-monospace"
      :append-inner-icon="copyIcon(sandbox.host)" @click:append-inner="copy(sandbox.host)"
    />
    <v-text-field
      v-if="sandbox.workdir" :model-value="sandbox.workdir" label="Folder" readonly variant="outlined" density="compact" hide-details class="font-monospace"
      :append-inner-icon="copyIcon(sandbox.workdir)" @click:append-inner="copy(sandbox.workdir)"
    />
  </div>
</template>
