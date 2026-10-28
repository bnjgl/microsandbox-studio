<script setup>
import { computed } from 'vue'
import { hosts, newSecret, newVariable, once, required, variableName } from '../sandbox'

const rows = defineModel({ type: Object, required: true })
defineProps({ disabled: Boolean })

const names = computed(() => [...rows.value.variables, ...rows.value.secrets].map(row => row.name))
</script>

<template>
  <div class="d-flex align-center justify-space-between mb-2">
    <span class="text-title-small font-weight-bold">Variables</span>
    <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="disabled" @click="rows.variables.push(newVariable())">Variable</v-btn>
  </div>
  <v-row v-for="(row, index) in rows.variables" :key="`v${index}`" dense align="center">
    <v-col cols="5"><v-text-field v-model="row.name" label="Name" variant="outlined" density="compact" hide-details="auto" :rules="[variableName, once(names, 'Used twice')]" class="font-monospace" :disabled="disabled" /></v-col>
    <v-col cols="6"><v-text-field v-model="row.value" label="Value" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
    <v-col cols="1" class="text-right"><v-btn icon="mdi-close" size="small" variant="text" aria-label="Remove variable" :disabled="disabled" @click="rows.variables.splice(index, 1)" /></v-col>
  </v-row>

  <div class="d-flex align-center justify-space-between mt-6 mb-1">
    <span class="text-title-small font-weight-bold">Secrets</span>
    <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="disabled" @click="rows.secrets.push(newSecret())">Secret</v-btn>
  </div>
  <p class="text-body-small text-medium-emphasis mb-3">
    Programs in the sandbox only see a placeholder; Microsandbox puts in the real value on the way to the allowed hosts.
  </p>
  <v-row v-for="(row, index) in rows.secrets" :key="`s${index}`" dense align="center">
    <v-col cols="12" sm="3"><v-text-field v-model="row.name" label="Name" variant="outlined" density="compact" hide-details="auto" :rules="[variableName, once(names, 'Used twice')]" class="font-monospace" :disabled="disabled" /></v-col>
    <v-col cols="12" sm="4"><v-text-field v-model="row.value" label="Value" type="password" variant="outlined" density="compact" hide-details="auto" :rules="[required]" :disabled="disabled" /></v-col>
    <v-col cols="11" sm="4"><v-text-field v-model="row.allow" label="Allowed hosts" placeholder="api.example.com" variant="outlined" density="compact" hide-details="auto" :rules="[hosts]" :disabled="disabled" /></v-col>
    <v-col cols="1" class="text-right"><v-btn icon="mdi-close" size="small" variant="text" aria-label="Remove secret" :disabled="disabled" @click="rows.secrets.splice(index, 1)" /></v-col>
  </v-row>
</template>
