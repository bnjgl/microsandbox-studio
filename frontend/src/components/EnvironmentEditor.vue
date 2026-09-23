<script setup>
// One settings object, two views: the form rows and the YAML text. A valid edit
// in either view replaces the settings and rewrites the other view.
// Renders the body and actions of a card; the parent provides card and title.
// Settings are loaded when the editor is mounted.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, useEnvironment } from '../api'
import { VIOLATION_ACTIONS, needsRestart, savedMessage, summary } from '../environment'
import { sameJson } from '../util'

const props = defineProps({
  sandbox: { type: String, default: null }, // null while creating a new sandbox
  initial: { type: Object, default: null }, // settings for a new sandbox; empty if not given
})
const emit = defineEmits(['apply', 'saved', 'cancel', 'busy'])

const { locations, createOnlyChange, emptySettings, fromRows, newRow, parseYaml, toRows, toYaml } = useEnvironment()
const tab = ref('gui')
const settings = ref(emptySettings()), original = ref(emptySettings())
const rows = ref([]), globalAction = ref(emptySettings().secret_violation_action), yamlText = ref('')
const formError = ref(''), yamlError = ref(''), error = ref('')
const status = ref('new'), revision = ref(''), loading = ref(false), saving = ref(false)
const revealed = ref(new Set())

const existing = computed(() => !!props.sandbox)
const locked = computed(() => existing.value || saving.value)
const lockedHint = 'The Python SDK only allows changing this on creation.'
const createOnlyError = computed(() => existing.value ? createOnlyChange(settings.value, original.value) : '')
const restart = computed(() => needsRestart(settings.value, original.value, status.value))
const canSave = computed(() => !loading.value && !saving.value && !formError.value && !yamlError.value && !createOnlyError.value)
const counts = computed(() => summary(settings.value))

function show(next) {
  settings.value = next
  rows.value = toRows(next)
  globalAction.value = next.secret_violation_action
  yamlText.value = toYaml(next)
  formError.value = yamlError.value = ''
}

watch([rows, globalAction], () => {
  try {
    const next = fromRows(rows.value, globalAction.value)
    formError.value = ''
    if (sameJson(next, settings.value)) return
    settings.value = next
    yamlText.value = toYaml(next)
    yamlError.value = ''
  } catch (e) { formError.value = e.message }
}, { deep: true })

function editYaml(text) {
  yamlText.value = text
  try {
    const next = parseYaml(text)
    yamlError.value = ''
    if (sameJson(next, settings.value)) return
    settings.value = next
    rows.value = toRows(next)
    globalAction.value = next.secret_violation_action
    formError.value = ''
  } catch (e) { yamlError.value = e.message }
}

watch(() => loading.value || saving.value, busy => emit('busy', busy))
// The parent switches pages right after 'saved', so the watcher above never reports the end of saving.
onBeforeUnmount(() => emit('busy', false))

onMounted(async () => {
  if (!existing.value) { show(props.initial ?? emptySettings()); return }
  loading.value = true
  try {
    const data = await api().get_environment(props.sandbox)
    show(data.settings); original.value = settings.value
    status.value = data.status; revision.value = data.revision
  } catch (e) { error.value = String(e) }
  finally { loading.value = false }
})

function toggleReveal(id) {
  const next = new Set(revealed.value)
  next.has(id) ? next.delete(id) : next.add(id)
  revealed.value = next
}

async function save() {
  if (!existing.value) { emit('apply', settings.value); return }
  saving.value = true; error.value = ''
  try {
    const result = await api().save_environment(props.sandbox, settings.value, revision.value)
    emit('saved', savedMessage(result, status.value), result)
  } catch (e) { error.value = String(e) }
  finally { saving.value = false }
}
</script>

<template>
  <div class="d-flex align-center px-3 mt-2">
    <v-tabs v-model="tab" :disabled="loading || saving">
      <v-tab value="gui" prepend-icon="mdi-form-select">GUI</v-tab>
      <v-tab value="yaml" prepend-icon="mdi-code-braces">YAML</v-tab>
    </v-tabs>
    <v-spacer />
    <span class="text-body-small text-medium-emphasis px-3">{{ counts }}</span>
  </div>
  <v-divider />
  <v-card-text class="px-6 pt-5">
    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
    <v-alert v-if="createOnlyError" type="error" variant="tonal" class="mb-4">{{ createOnlyError }}</v-alert>
    <template v-if="!loading">
      <p class="text-body-medium text-medium-emphasis mb-4">Programs can read variables directly. For secrets, the sandbox only sees a placeholder; the real value is inserted only in requests to allowed hosts.</p>

      <v-window v-model="tab">
        <v-window-item value="gui">
          <v-alert v-if="formError" type="error" variant="tonal" class="mb-4">{{ formError }}</v-alert>
          <v-alert v-else-if="yamlError" type="warning" variant="tonal" class="mb-4">The YAML contains an error. The form shows the last valid state; a change here overwrites the YAML.</v-alert>

          <v-card v-for="(row, index) in rows" :key="row.id" variant="outlined" class="mb-3">
            <v-card-text class="pb-2">
              <v-row dense align="start">
                <v-col cols="12" sm="3">
                  <v-select v-model="row.kind" label="Type" :items="[{ title: 'Variable', value: 'env' }, { title: 'Secret', value: 'secret' }]" variant="outlined" density="compact" hide-details :disabled="saving" />
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field v-model="row.key" label="Name" placeholder="API_KEY" variant="outlined" density="compact" hide-details spellcheck="false" :disabled="saving" />
                </v-col>
                <v-col cols="10" sm="4">
                  <v-text-field v-if="row.kind === 'secret'" v-model="row.value" label="Value" :placeholder="`\${${row.key || 'NAME'}}`" :type="revealed.has(row.id) ? 'text' : 'password'" :append-inner-icon="revealed.has(row.id) ? 'mdi-eye-off' : 'mdi-eye'" variant="outlined" density="compact" hide-details autocomplete="off" :disabled="saving" @click:append-inner="toggleReveal(row.id)" />
                  <v-textarea v-else v-model="row.value" label="Value" variant="outlined" density="compact" hide-details auto-grow rows="1" max-rows="5" spellcheck="false" autocomplete="off" :disabled="saving" />
                </v-col>
                <v-col cols="2" sm="1">
                  <v-btn icon="mdi-close" variant="text" size="small" aria-label="Remove entry" :disabled="saving" @click="rows.splice(index, 1)" />
                </v-col>
              </v-row>
              <template v-if="row.kind === 'secret'">
                <p class="text-body-small text-medium-emphasis mt-2">Leave empty to use the host variable {{ row.key || 'of the same name' }}. <code>${NAME}</code> refers to another host variable without storing its value.</p>
                <v-combobox v-model="row.allow" label="Allowed hosts (allow)" placeholder="api.example.com" multiple chips closable-chips variant="outlined" density="compact" class="mt-4" hint="Type a host and press Enter to add it. *.example.com also allows subdomains." persistent-hint :disabled="saving" />
                <v-expansion-panels variant="accordion" class="my-2">
                  <v-expansion-panel title="More secret options">
                    <v-expansion-panel-text>
                      <p v-if="existing" class="text-body-small text-medium-emphasis mb-3">{{ lockedHint }}</p>
                      <div class="text-body-medium mb-1">Substitute in (substitution)</div>
                      <div class="d-flex flex-wrap ga-4">
                        <v-checkbox v-for="location in locations" :key="location" v-model="row.substitution[location]" :label="location" hide-details density="compact" :disabled="locked" />
                      </div>
                      <v-combobox v-model="row.passthrough" label="Allow the placeholder unchanged for (passthrough)" multiple chips closable-chips variant="outlined" density="compact" class="mt-3" :disabled="locked" />
                      <v-select v-model="row.violation_action" label="On violation (violation_action)" :items="[{ title: 'Use global rule', value: null }, ...VIOLATION_ACTIONS]" variant="outlined" density="compact" :disabled="locked" />
                      <v-checkbox v-model="row.require_tls_identity" label="Require verified TLS identity (require_tls_identity)" hide-details density="compact" :disabled="locked" />
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>
              </template>
            </v-card-text>
          </v-card>
          <p v-if="!rows.length" class="text-body-medium text-medium-emphasis mb-4">No entries yet.</p>

          <div class="d-flex flex-wrap ga-2 mb-5">
            <v-btn variant="tonal" prepend-icon="mdi-plus" :disabled="saving" @click="rows.push(newRow('env'))">Variable</v-btn>
            <v-btn variant="tonal" prepend-icon="mdi-key-plus" :disabled="saving" @click="rows.push(newRow('secret'))">Secret</v-btn>
          </div>
          <v-select v-model="globalAction" label="Global rule for violations (secret_violation_action)" :items="VIOLATION_ACTIONS" variant="outlined" density="compact" :hint="existing ? lockedHint : ''" :persistent-hint="existing" :disabled="locked" />
        </v-window-item>

        <v-window-item value="yaml">
          <v-alert v-if="yamlError" type="error" variant="tonal" class="mb-4">{{ yamlError }}</v-alert>
          <v-alert v-else-if="formError" type="warning" variant="tonal" class="mb-4">The form contains an error. The YAML shows the last valid state; a change here overwrites the form.</v-alert>
          <v-textarea :model-value="yamlText" label="YAML" placeholder="env:&#10;  MODE: &quot;development&quot;&#10;secrets:&#10;  GITHUB_TOKEN:&#10;    value: &quot;${GITHUB_TOKEN}&quot;&#10;    allow: [&quot;api.github.com&quot;]" variant="outlined" rows="16" auto-grow spellcheck="false" autocomplete="off" style="font-family: monospace" :disabled="saving" @update:model-value="editYaml" />
          <p class="text-body-small text-medium-emphasis">
            Allowed are <code>env</code>, <code>secrets</code> and <code>secret_violation_action</code>, as in the
            <a href="https://docs.microsandbox.dev/sandboxes/secrets#yaml-configuration" target="_blank">Microsandbox documentation</a>.
            Without <code>value</code>, the host variable of the same name is used. Anchors, aliases, custom tags and unquoted yes/no/on/off are rejected.
            Values are shown here in plain text.
          </p>
        </v-window-item>
      </v-window>

      <v-alert v-if="restart" type="info" variant="tonal" class="mt-4">New secrets require a restart. Running processes are stopped; the shell reconnects afterwards.</v-alert>
    </template>
  </v-card-text>
  <v-card-actions class="px-6 pb-6">
    <v-spacer />
    <v-btn variant="text" :disabled="loading || saving" @click="emit('cancel')">Cancel</v-btn>
    <v-btn color="primary" :loading="saving" :disabled="!canSave || (existing && !revision)" @click="save">
      {{ !existing ? 'Apply' : restart ? 'Save & restart' : 'Save' }}
    </v-btn>
  </v-card-actions>
</template>
