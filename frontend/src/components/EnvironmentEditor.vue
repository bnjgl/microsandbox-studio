<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../bridge'
import { useTask } from '../composables'
import { fromRows, toRows } from '../sandbox'
import EnvironmentForm from './EnvironmentForm.vue'

const props = defineProps({ sandbox: { type: Object, required: true } })
const emit = defineEmits(['saved', 'cancel'])

const rows = ref(null), formRef = ref(null)
const { busy, error, run } = useTask()

onMounted(() => run(async () => { rows.value = toRows(await api().get_environment(props.sandbox.name)) }))

async function save() {
  if (!(await formRef.value.validate()).valid) return
  return run(async () => {
    await api().save_environment(props.sandbox.name, fromRows(rows.value))
    emit('saved', 'Variables and secrets saved.')
  })
}
</script>

<template>
  <v-card-text class="px-6 pt-5">
    <v-progress-linear v-if="!rows && busy" indeterminate color="primary" class="mb-4" />
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4 text-pre-wrap">{{ error }}</v-alert>
    <v-form v-if="rows" ref="formRef" validate-on="blur"><EnvironmentForm v-model="rows" :disabled="busy" /></v-form>
    <p v-if="rows && sandbox.status === 'running'" class="text-body-small text-medium-emphasis mt-4">
      The sandbox restarts if the change needs it; open shells see new variables only after reconnecting.
    </p>
  </v-card-text>
  <v-card-actions class="px-6 pb-6">
    <v-spacer />
    <v-btn variant="text" :disabled="busy" @click="emit('cancel')">Cancel</v-btn>
    <v-btn color="primary" :loading="busy" :disabled="!rows" @click="save">Save</v-btn>
  </v-card-actions>
</template>
