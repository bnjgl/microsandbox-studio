<script setup>
// Search for an agent or tool and run its install command in the terminal.
// The command is shown first, so nothing is piped into a shell unseen.
import { ref, watch } from 'vue'
import { TOOLS, matchesTool } from '../tools'

defineProps({ disabled: Boolean })
const emit = defineEmits(['install'])

const open = ref(false), tool = ref(null)
watch(open, value => { if (!value) tool.value = null })

function install() {
  emit('install', tool.value.command)
  open.value = false
}
</script>

<template>
  <v-menu v-model="open" location="bottom end" :close-on-content-click="false" :disabled="disabled">
    <template #activator="{ props: menu }">
      <v-tooltip :text="disabled ? 'Start the sandbox to install tools' : 'Install agents and tools'" location="bottom">
        <template #activator="{ props: tooltip }">
          <!-- Disabled buttons get no hover events, so the tooltip hangs on a wrapper. -->
          <span v-bind="tooltip"><v-btn v-bind="menu" icon="mdi-package-variant-plus" variant="text" size="small" aria-label="Install agents and tools" :disabled="disabled" /></span>
        </template>
      </v-tooltip>
    </template>
    <v-card rounded="lg" color="surface" border width="400" class="pa-3">
      <v-autocomplete
        v-model="tool" :items="TOOLS" item-title="name" return-object autofocus auto-select-first
        :custom-filter="(_value, query, item) => matchesTool(item.raw ?? item, query)"
        placeholder="Search, e.g. claude, uv, node" prepend-inner-icon="mdi-magnify"
        density="compact" variant="outlined" hide-details
      >
        <template #item="{ props: itemProps, item }">
          <v-list-item v-bind="itemProps" :subtitle="`${item.group} · ${item.description}`" />
        </template>
      </v-autocomplete>
      <template v-if="tool">
        <div class="text-caption text-medium-emphasis mt-3 mb-1">Runs in the terminal:</div>
        <code class="d-block pa-2 rounded text-caption" style="background: #090F1C; word-break: break-all">{{ tool.command }}</code>
        <div class="d-flex justify-end mt-3">
          <v-btn color="primary" size="small" prepend-icon="mdi-download" @click="install">Install</v-btn>
        </div>
      </template>
    </v-card>
  </v-menu>
</template>
