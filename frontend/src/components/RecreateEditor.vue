<script setup>
// Frame for settings of an existing sandbox that Microsandbox can only change
// by re-creating it (network, workspace folders). Loads the settings when
// mounted, shows why re-creating would be refused, and saves only after an
// explicit confirmation that lists every step. Renders the body and actions
// of a card; the parent provides card and title, the form goes into the slot.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { savedMessage } from '../recreate'

const props = defineProps({
  sandbox: { type: String, required: true },
  what: { type: String, required: true }, // e.g. 'the network', completes "Microsandbox cannot change … of an existing sandbox"
  label: { type: String, required: true }, // e.g. 'Network', for the saved message
  load: { type: Function, required: true }, // () => { status, revision, problem, kept, … }
  save: { type: Function, required: true }, // revision => { changed, restarted }
  changed: Boolean,
  editable: { type: Boolean, default: true }, // false: the parent explains why
})
const emit = defineEmits(['loaded', 'saved', 'recreated', 'cancel', 'busy'])

const status = ref(''), revision = ref(''), problem = ref(''), kept = ref('')
const loading = ref(true), saving = ref(false), confirming = ref(false), error = ref('')
const running = computed(() => status.value !== 'stopped')

watch(() => loading.value || saving.value, busy => emit('busy', busy), { immediate: true })
// The parent switches pages right after 'saved', so the watcher above never reports the end of saving.
onBeforeUnmount(() => emit('busy', false))

onMounted(async () => {
  try {
    const data = await props.load()
    status.value = data.status; revision.value = data.revision; problem.value = data.problem || ''; kept.value = data.kept
    emit('loaded', data)
  } catch (e) { error.value = String(e) }
  finally { loading.value = false }
})

async function recreate() {
  confirming.value = false; saving.value = true; error.value = ''
  try {
    const result = await props.save(revision.value)
    emit('saved', savedMessage(props.label, result), { ...result, recreated: result.changed })
  } catch (e) {
    error.value = String(e)
    // A rollback re-creates the sandbox as well, so the list must be reloaded.
    emit('recreated')
  } finally { saving.value = false }
}
</script>

<template>
  <v-card-text class="px-6 pt-5">
    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4 text-pre-wrap">{{ error }}</v-alert>
    <v-alert v-if="saving" type="info" variant="tonal" class="mb-4" icon="mdi-progress-clock">
      Rebuilding the sandbox. Please keep the window open; this can take from a few seconds to a few minutes.
    </v-alert>

    <template v-if="!loading">
      <template v-if="editable">
        <v-alert v-if="problem" type="warning" variant="tonal" class="mb-4 text-pre-wrap">
          {{ problem }}
          <div class="mt-2">That is why it cannot be changed here.</div>
        </v-alert>
        <v-alert type="info" variant="tonal" density="compact" class="mb-4" icon="mdi-information-outline">
          Microsandbox cannot change {{ what }} of an existing sandbox. Applying rebuilds the sandbox; the app shows exactly what happens beforehand.
        </v-alert>
      </template>
      <slot :disabled="saving" />
    </template>
  </v-card-text>
  <v-card-actions class="px-6 pb-6">
    <v-spacer />
    <v-btn variant="text" :disabled="saving" @click="emit('cancel')">Back</v-btn>
    <v-btn color="primary" :loading="saving" :disabled="loading || !editable || !!problem || !changed" @click="confirming = true">Apply …</v-btn>
  </v-card-actions>

  <v-dialog v-model="confirming" max-width="560">
    <v-card rounded="xl" color="surface">
      <v-card-title class="px-6 pt-6">Rebuild sandbox?</v-card-title>
      <v-card-text class="px-6">
        <p class="mb-3">Microsandbox cannot change {{ what }} of an existing sandbox, so the app rebuilds “{{ sandbox }}”:</p>
        <ol class="pl-5 mb-3">
          <li v-if="running">The shell is disconnected and the sandbox stopped. <strong>Running programs and the shell session end</strong>; unsaved work in the sandbox is lost.</li>
          <li>The app saves the files of the sandbox in a snapshot.</li>
          <li>The sandbox is deleted and re-created from the snapshot under the same name, with the new settings.</li>
          <li>Carried over: {{ kept }}. The internal ID changes; the display name stays.</li>
          <li>{{ running ? 'Afterwards the sandbox runs again and the shell reconnects, with a new session.' : 'Afterwards the sandbox is stopped again.' }}</li>
          <li>Finally, the snapshot is deleted.</li>
        </ol>
        <p class="text-medium-emphasis">If a step fails, the app restores the sandbox with its previous settings. If that fails too, the snapshot is kept and the error message names it.</p>
      </v-card-text>
      <v-card-actions class="px-6 pb-6">
        <v-spacer />
        <v-btn variant="text" @click="confirming = false">Cancel</v-btn>
        <v-btn color="primary" @click="recreate">Rebuild</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
