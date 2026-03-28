import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/global.scss'
import App from './App.vue'
import router from './router'
import { useTheme } from './composables/useTheme'

// Initialize theme before mount
const { initTheme } = useTheme()
initTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
