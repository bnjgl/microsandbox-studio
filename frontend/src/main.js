import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import App from './App.vue'

const vuetify = createVuetify({
  icons: { defaultSet: 'mdi' },
  theme: { defaultTheme: 'studio', themes: { studio: { dark: true, colors: {
    background: '#0B1020', surface: '#111A2C', 'surface-bright': '#1B2940',
    primary: '#75E1C2', secondary: '#94A7C4', error: '#FF7D86'
  } } } }
})
createApp(App).use(vuetify).mount('#app')
