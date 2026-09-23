<script setup>
// Variables and secrets for a sandbox that is being created.
import { ref } from 'vue'
import EnvironmentEditor from './EnvironmentEditor.vue'

const open = defineModel({ type: Boolean })
defineProps({ initial: { type: Object, required: true } })
const emit = defineEmits(['apply'])
const busy = ref(false)

function apply(settings) { emit('apply', settings); open.value = false }
</script>

<template>
  <v-dialog v-model="open" max-width="960" :persistent="busy" scrollable>
    <v-card rounded="xl" color="surface">
      <v-card-title class="px-6 pt-6">Variables &amp; secrets · New sandbox</v-card-title>
      <EnvironmentEditor v-if="open" :initial="initial" @apply="apply" @cancel="open = false" @busy="value => busy = value" />
    </v-card>
  </v-dialog>
</template>
