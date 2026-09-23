<script setup>
// Network settings for a sandbox that is being created.
import { ref, watch } from 'vue'
import { toSettings } from '../network'
import { clone } from '../util'
import NetworkForm from './NetworkForm.vue'

const open = defineModel({ type: Boolean })
const props = defineProps({ initial: { type: Object, required: true } })
const emit = defineEmits(['apply'])

const form = ref(clone(props.initial))
watch(open, isOpen => { if (isOpen) form.value = clone(props.initial) })

function apply() { emit('apply', toSettings(form.value)); open.value = false }
</script>

<template>
  <v-dialog v-model="open" max-width="820" scrollable>
    <v-card rounded="xl" color="surface">
      <v-card-title class="px-6 pt-6">Network · New sandbox</v-card-title>
      <v-card-text class="px-6 pt-5"><NetworkForm v-model="form" /></v-card-text>
      <v-card-actions class="px-6 pb-6">
        <v-spacer />
        <v-btn variant="text" @click="open = false">Cancel</v-btn>
        <v-btn color="primary" @click="apply">Apply</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
