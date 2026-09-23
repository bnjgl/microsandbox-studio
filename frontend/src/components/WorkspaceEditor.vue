<script setup>
// Workspace folders of an existing sandbox. Microsandbox cannot change mounts,
// so saving re-creates the sandbox (see RecreateEditor).
import { computed, ref } from 'vue'
import { api } from '../api'
import { sameJson } from '../util'
import RecreateEditor from './RecreateEditor.vue'
import WorkspaceFolders from './WorkspaceFolders.vue'

const props = defineProps({ sandbox: { type: String, required: true } })
const emit = defineEmits(['saved', 'recreated', 'cancel', 'busy'])

const folders = ref([]), original = ref([]), picking = ref(false)
const changed = computed(() => !picking.value && !sameJson(folders.value, original.value))

function loaded(data) { folders.value = data.folders; original.value = data.folders }
</script>

<template>
  <RecreateEditor
    v-slot="{ disabled }" :sandbox="sandbox" what="the workspace folders" label="Workspace folders" :changed="changed"
    :load="() => api().get_workspaces(sandbox)" :save="revision => api().save_workspaces(sandbox, folders, revision)"
    @loaded="loaded" @saved="(...args) => emit('saved', ...args)" @recreated="emit('recreated')" @cancel="emit('cancel')" @busy="value => emit('busy', value)"
  >
    <WorkspaceFolders v-model="folders" :disabled="disabled" @busy="value => picking = value" />
    <p v-if="!folders.length" class="text-body-medium text-medium-emphasis">No workspace folders mounted.</p>
    <p class="text-body-small text-medium-emphasis mt-3">Removed folders stay on this computer; only their mount in the sandbox goes away.</p>
  </RecreateEditor>
</template>
