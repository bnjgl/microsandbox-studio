import { ref } from 'vue'

export function useTask() {
  const busy = ref(false), error = ref('')
  async function run(task) {
    busy.value = true; error.value = ''
    try { return await task() } catch (e) { error.value = String(e) } finally { busy.value = false }
  }
  return { busy, error, run }
}

export function useCopy() {
  const copied = ref('')
  async function copy(text) {
    await navigator.clipboard.writeText(text)
    copied.value = text
  }
  const copyIcon = text => copied.value === text ? 'mdi-check' : 'mdi-content-copy'
  return { copy, copyIcon }
}
