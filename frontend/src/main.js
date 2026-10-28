import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import './styles.css'
import App from './App.vue'

const square = { rounded: 'sm' }
const vuetify = createVuetify({
  icons: { defaultSet: 'mdi' },
  theme: { defaultTheme: 'studio', themes: { studio: {
    dark: true,
    colors: {
      background: '#08080B', surface: '#0E0D12', 'surface-bright': '#17151D', 'surface-light': '#17151D',
      primary: '#C084FC', secondary: '#A3A3AD', info: '#D8B4FE', warning: '#FBBF24', error: '#F87171',
    },
    variables: { 'border-color': '#FFFFFF', 'border-opacity': 0.09 },
  } } },
  defaults: {
    VAlert: square, VBtn: square, VCard: square, VChip: square, VSelect: square, VTextField: square,
    VSwitch: { color: 'primary' },
    VDialog: { opacity: 0.75 },
  },
})
createApp(App).use(vuetify).mount('#app')
