<script setup>
// Form fields for network access, own rules and published ports.
// Used when creating a sandbox (NetworkDialog) and in its settings (NetworkEditor).
import { computed } from 'vue'
import { ACTIONS, BINDS, MODES, PROFILES, PROTOCOLS, blocksEverything, exposes, newPort, newRule } from '../network'

const form = defineModel({ type: Object, required: true })
defineProps({ disabled: Boolean })

const exposed = computed(() => exposes(form.value.ports))
</script>

<template>
  <div class="text-title-medium font-weight-bold mb-2">Access</div>
  <v-radio-group v-model="form.mode" :disabled="disabled" hide-details class="mb-2">
    <v-radio v-for="mode in MODES" :key="mode.value" :value="mode.value" color="primary">
      <template #label>
        <div><div>{{ mode.title }}</div><div class="text-body-small text-medium-emphasis">{{ mode.text }}</div></div>
      </template>
    </v-radio>
  </v-radio-group>

  <template v-if="form.mode === 'restricted'">
    <div class="text-title-small font-weight-bold mt-4 mb-1">Allowed zones</div>
    <v-checkbox
      v-for="profile in PROFILES" :key="profile.value" v-model="form.profiles" :value="profile.value"
      color="primary" density="compact" hide-details :disabled="disabled"
    >
      <template #label><span>{{ profile.title }} <span class="text-body-small text-medium-emphasis">· {{ profile.text }}</span></span></template>
    </v-checkbox>

    <div class="d-flex align-center justify-space-between mt-5 mb-1">
      <span class="text-title-small font-weight-bold">Custom rules</span>
      <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="disabled" @click="form.rules.push(newRule())">Rule</v-btn>
    </div>
    <p class="text-body-small text-medium-emphasis mb-3">
      For outgoing connections. The target is a domain (api.example.com), a suffix with a leading dot (.example.com), an IP address or a CIDR range.
      Rules apply before the zones above, and the first match wins. This lets you, for example, block a domain on the internet or allow single hosts without internet access.
    </p>
    <v-row v-for="(rule, index) in form.rules" :key="index" dense align="center">
      <v-col cols="12" sm="3"><v-select v-model="rule.action" :items="ACTIONS" label="Action" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
      <v-col cols="12" sm="4"><v-text-field v-model="rule.target" label="Target" placeholder="api.example.com" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
      <v-col cols="5" sm="2"><v-select v-model="rule.protocol" :items="PROTOCOLS" label="Protocol" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
      <v-col cols="5" sm="2"><v-text-field v-model="rule.port" label="Port" placeholder="all" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
      <v-col cols="2" sm="1" class="text-right"><v-btn icon="mdi-close" size="small" variant="text" aria-label="Remove rule" :disabled="disabled" @click="form.rules.splice(index, 1)" /></v-col>
    </v-row>
    <v-alert v-if="blocksEverything(form)" type="warning" variant="tonal" density="compact" class="mt-3">
      Without a zone and without an allow rule, no outgoing connections are possible.
    </v-alert>
  </template>

  <div class="d-flex align-center justify-space-between mt-6 mb-1">
    <span class="text-title-medium font-weight-bold">Port mappings</span>
    <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="disabled" @click="form.ports.push(newPort())">Port</v-btn>
  </div>
  <p class="text-body-small text-medium-emphasis mb-3">Makes a service in the sandbox reachable on this computer, e.g. host port 8080 → sandbox port 80. By default only on localhost (127.0.0.1).</p>
  <v-row v-for="(port, index) in form.ports" :key="index" dense align="center">
    <v-col cols="6" sm="2"><v-text-field v-model="port.host_port" label="Host port" placeholder="8080" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
    <v-col cols="6" sm="2"><v-text-field v-model="port.guest_port" label="Sandbox port" placeholder="80" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
    <v-col cols="5" sm="3"><v-select v-model="port.protocol" :items="PROTOCOLS.slice(1)" label="Protocol" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
    <v-col cols="5" sm="4"><v-combobox v-model="port.bind" :items="BINDS" label="Bind address" variant="outlined" density="compact" hide-details :disabled="disabled" /></v-col>
    <v-col cols="2" sm="1" class="text-right"><v-btn icon="mdi-close" size="small" variant="text" aria-label="Remove port mapping" :disabled="disabled" @click="form.ports.splice(index, 1)" /></v-col>
  </v-row>
  <v-alert v-if="exposed" type="warning" variant="tonal" density="compact" class="mt-3">
    A bind address other than 127.0.0.1 makes the port reachable from other devices on the network, as far as the firewall allows.
  </v-alert>
  <v-alert v-if="form.mode === 'none' && form.ports.length" type="warning" variant="tonal" density="compact" class="mt-3">
    “No network” also blocks incoming connections; the port mappings are then unreachable.
  </v-alert>
</template>
