import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  build: { outDir: '../src/microsandbox_studio/frontend', emptyOutDir: true },
  plugins: [vue(), vuetify({ autoImport: true })],
})
