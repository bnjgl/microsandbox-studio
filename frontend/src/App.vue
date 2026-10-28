<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { api, bridgeReady } from './bridge'
import { useCopy } from './composables'
import { count } from './sandbox'
import logo from './assets/logo.svg'
import SandboxCard from './components/SandboxCard.vue'

const CreateDialog = defineAsyncComponent(() => import('./components/CreateDialog.vue'))

const sandboxes = ref([]), limit = ref(Infinity), loaded = ref(false), loading = ref(false), creating = ref(false)
const ssh = ref({ on: false, included: false, include: '', config: '' }), sshDialog = ref(false), settingUp = ref(false)
const toast = ref({ show: false, text: '', color: '' })

const full = computed(() => sandboxes.value.length >= limit.value)
const year = new Date().getFullYear()

const { copy, copyIcon } = useCopy()

const notify = (text, color = 'success') => { toast.value = { show: true, text, color } }

async function refresh() {
  loading.value = true
  try {
    const [list, state] = await Promise.all([api().list_sandboxes(), api().get_ssh()])
    sandboxes.value = list.sandboxes; limit.value = list.limit; ssh.value = state; loaded.value = true
  }
  catch (e) { notify(String(e), 'error') }
  finally { loading.value = false }
}

async function toggleSsh() {
  settingUp.value = true
  try {
    if (ssh.value.on) { await api().remove_ssh(); notify('SSH turned off.') }
    else { await api().set_up_ssh(); notify('SSH turned on.') }
    sshDialog.value = false
    refresh()
  } catch (e) { notify(String(e), 'error') }
  finally { settingUp.value = false }
}

onMounted(() => bridgeReady().then(refresh))
</script>

<template>
  <v-app>
    <v-app-bar flat density="compact" color="background" border="b">
      <img :src="logo" alt="" width="30" height="30" class="ml-4 mr-3">
      <v-app-bar-title class="font-pixel ml-0">
        microsandbox <span class="text-primary">studio</span>
      </v-app-bar-title>
      <v-switch
        :model-value="ssh.on" label="Use SSH" color="success" base-color="error" inset size="x-small" hide-details density="compact"
        class="flex-grow-0 mr-6" @update:model-value="sshDialog = true"
      />
      <v-btn class="mr-3" color="primary" variant="tonal" prepend-icon="mdi-plus" :disabled="full" @click="creating = true">New sandbox</v-btn>
    </v-app-bar>

    <v-main>
      <v-container fluid class="pa-4">
        <v-alert v-if="full" type="info" variant="tonal" density="compact" class="mb-4">
          Microsandbox Studio shows up to {{ limit }} sandboxes. Delete one to create a new one.
        </v-alert>
        <v-alert v-if="ssh.on && !ssh.included" type="warning" variant="tonal" class="mb-4">
          Add this line at the very top of <code>{{ ssh.config }}</code>, above any <code>Host</code> or <code>Match</code>, then click refresh.
          <v-text-field
            :model-value="ssh.include" readonly variant="outlined" density="compact" hide-details class="font-monospace mt-3"
            :append-inner-icon="copyIcon(ssh.include)" @click:append-inner="copy(ssh.include).catch(e => notify(String(e), 'error'))"
          />
        </v-alert>
        <v-row v-if="sandboxes.length">
          <v-col v-for="sandbox in sandboxes" :key="sandbox.name" cols="12" md="6" lg="4" xl="3">
            <SandboxCard :sandbox="sandbox" :ssh="ssh" @changed="refresh" @notify="notify" />
          </v-col>
        </v-row>

        <div v-else-if="loaded" class="d-flex justify-center pt-16">
          <v-card color="surface" border max-width="460" class="text-center pa-8">
            <img :src="logo" alt="" width="96" height="96" class="mb-5">
            <h1 class="text-headline-small font-pixel mb-2">no sandboxes yet.</h1>
            <p class="text-body-large text-medium-emphasis mb-6">Create a sandbox, then reach it over SSH from your terminal, editor or agent harness.</p>
            <v-btn color="primary" size="large" prepend-icon="mdi-plus" @click="creating = true">Create sandbox</v-btn>
          </v-card>
        </div>
      </v-container>
    </v-main>

    <v-footer app color="background" border="t" class="text-body-small text-medium-emphasis py-1">
      © {{ year }} Microsandbox Studio
      <v-chip size="x-small" variant="outlined" class="ml-2" title="A community GUI over the Microsandbox SDK; not made by the Microsandbox team.">unofficial</v-chip>
      <v-spacer />
      {{ count(sandboxes.length, 'sandbox', 'sandboxes') }}
      <v-btn icon="mdi-refresh" variant="text" size="x-small" class="ml-1" :loading="loading" aria-label="Refresh" @click="refresh" />
    </v-footer>

    <v-snackbar v-model="toast.show" :color="toast.color" :timeout="toast.color === 'error' ? -1 : 4000" location="bottom right" multi-line>
      {{ toast.text }}
      <template #actions><v-btn icon="mdi-close" variant="text" size="small" aria-label="Close" @click="toast.show = false" /></template>
    </v-snackbar>

    <v-dialog v-model="sshDialog" max-width="480" :persistent="settingUp">
      <v-card color="surface">
        <v-card-title class="px-6 pt-6 font-pixel">{{ ssh.on ? 'Turn off SSH?' : 'Turn on SSH?' }}</v-card-title>
        <v-card-text v-if="ssh.on" class="px-6">
          The app deletes its key and its SSH config. You can also remove the Include line from your SSH config.
        </v-card-text>
        <v-card-text v-else class="px-6">
          Every sandbox becomes reachable as <code>&lt;name&gt;.msb</code> for a terminal, an editor or an agent.
          The app creates a key, authorizes it with Microsandbox and writes its own SSH config.
          You then add one Include line to your SSH config.
        </v-card-text>
        <v-card-actions class="px-6 pb-6">
          <v-spacer />
          <v-btn variant="text" :disabled="settingUp" @click="sshDialog = false">Cancel</v-btn>
          <v-btn :color="ssh.on ? 'error' : 'primary'" variant="flat" :loading="settingUp" @click="toggleSsh">{{ ssh.on ? 'Turn off' : 'Turn on' }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <CreateDialog v-model="creating" @created="name => { notify(`${name} created.`); refresh() }" />
  </v-app>
</template>
