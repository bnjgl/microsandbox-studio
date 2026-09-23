import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  // The build ships inside the Python package, next to the other assets
  build: { outDir: '../src/microsandbox_studio/frontend', emptyOutDir: true },
  // autoImport pulls in only the Vuetify components the templates use
  plugins: [vue(), vuetify({ autoImport: true })],
})
