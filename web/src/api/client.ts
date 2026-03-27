import axios from 'axios'
import { useNovelStore } from '@/stores/novel'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Automatically inject novel_id query param
client.interceptors.request.use((config) => {
  try {
    const novelStore = useNovelStore()
    if (novelStore.activeNovelId) {
      config.params = {
        ...config.params,
        novel_id: novelStore.activeNovelId,
      }
    }
  } catch {
    // Pinia not ready yet
  }
  return config
})

export default client
