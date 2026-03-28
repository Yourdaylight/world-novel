import { ref, watch } from 'vue'

const isDark = ref(false)

// Initialize from localStorage or system preference
function initTheme() {
  const stored = localStorage.getItem('theme')
  if (stored === 'dark') {
    isDark.value = true
  } else if (stored === 'light') {
    isDark.value = false
  } else {
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme()
}

function applyTheme() {
  document.documentElement.classList.toggle('dark', isDark.value)
}

function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
  applyTheme()
}

// Watch for changes
watch(isDark, applyTheme)

export function useTheme() {
  return { isDark, toggleTheme, initTheme }
}
