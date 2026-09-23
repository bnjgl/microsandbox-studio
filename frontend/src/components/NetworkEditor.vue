<script setup>
// Network of an existing sandbox. Microsandbox cannot change it, so saving
// re-creates the sandbox (see RecreateEditor).
import { computed, ref } from 'vue'
import { api } from '../api'
import { defaultNetwork, toSettings } from '../network'
import { clone, sameJson } from '../util'
import NetworkForm from './NetworkForm.vue'
import RecreateEditor from './RecreateEditor.vue'

const props = defineProps({ sandbox: { type: String, required: true } })
const emit = defineEmits(['saved', 'recreated', 'cancel', 'busy'])

const form = ref(defaultNetwork()), original = ref(null), foreign = ref(false)
const changed = computed(() => !sameJson(toSettings(form.value), original.value))

function loaded(data) {
  if (data.settings) { form.value = clone(data.settings); original.value = data.settings } else foreign.value = true
}
</script>

<template>
  <RecreateEditor
    v-slot="{ disabled }" :sandbox="sandbox" what="the network" label="Network" :changed="changed" :editable="!foreign"
    :load="() => api().get_network(sandbox)" :save="revision => api().save_network(sandbox, toSettings(form), revision)"
    @loaded="loaded" @saved="(...args) => emit('saved', ...args)" @recreated="emit('recreated')" @cancel="emit('cancel')" @busy="value => emit('busy', value)"
  >
    <v-alert v-if="foreign" type="warning" variant="tonal">
      The network of this sandbox was set up outside the app, e.g. with the CLI, and cannot be shown here. Please change it with the CLI or SDK.
    </v-alert>
    <NetworkForm v-else v-model="form" :disabled="disabled" />
  </RecreateEditor>
</template>
