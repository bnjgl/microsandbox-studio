<script setup>
import { ref } from 'vue'
import { api } from '../bridge'
import { useTask } from '../composables'
import { CPU_CHOICES, MEMORY_CHOICES } from '../sandbox'

const props = defineProps({ sandbox: { type: Object, required: true } })
const emit = defineEmits(['saved', 'cancel'])

const cpus = ref(props.sandbox.cpus ?? 1), memory = ref(props.sandbox.memory ?? 1024)
const { busy, error, run } = useTask()

const save = () => run(async () => {
  await api().save_resources(props.sandbox.name, cpus.value, memory.value)
  emit('saved', 'Resources saved.')
})
</script>

<template>
  <v-card-text class="px-6 pt-5">
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4 text-pre-wrap">{{ error }}</v-alert>
    <v-row>
      <v-col cols="6"><v-select v-model="cpus" label="CPUs" :items="CPU_CHOICES" variant="outlined" :disabled="busy" /></v-col>
      <v-col cols="6"><v-select v-model="memory" label="Memory (MiB)" :items="MEMORY_CHOICES" variant="outlined" :disabled="busy" /></v-col>
    </v-row>
    <p v-if="sandbox.status === 'running'" class="text-body-small text-medium-emphasis">The sandbox restarts if the change needs it.</p>
  </v-card-text>
  <v-card-actions class="px-6 pb-6">
    <v-spacer />
    <v-btn variant="text" :disabled="busy" @click="emit('cancel')">Cancel</v-btn>
    <v-btn color="primary" :loading="busy" @click="save">Save</v-btn>
  </v-card-actions>
</template>
