import { ref } from 'vue'
import { useProgressStore } from '@/stores/progress'
import { useLiveWritingStore } from '@/stores/liveWriting'

let ws: WebSocket | null = null
const connected = ref(false)

// Event bus for component-level listeners
type EventCallback = (data: any) => void
const listeners: Record<string, EventCallback[]> = {}

export function onWSEvent(eventType: string, callback: EventCallback) {
  if (!listeners[eventType]) listeners[eventType] = []
  listeners[eventType].push(callback)
  // Return unsubscribe function
  return () => {
    const arr = listeners[eventType]
    if (arr) {
      const idx = arr.indexOf(callback)
      if (idx >= 0) arr.splice(idx, 1)
    }
  }
}

export function useWebSocket() {
  function connect() {
    if (ws) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws`
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      console.log('[WS] Connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        dispatch(data)
      } catch (e) {
        console.warn('[WS] Parse error:', e)
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
      // Auto-reconnect after 3s
      setTimeout(() => connect(), 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    ws?.close()
    ws = null
    connected.value = false
  }

  function dispatch(event: any) {
    const progressStore = useProgressStore()
    const liveWritingStore = useLiveWritingStore()

    // Route events to appropriate stores
    if (event.type === 'progress' || event.type === 'progress_update') {
      progressStore.updateFromWS(event)
    }

    // All events go to live writing for real-time display
    liveWritingStore.handleEvent(event)

    // Route to component-level listeners
    const eventType = event.type as string
    if (eventType && listeners[eventType]) {
      for (const cb of listeners[eventType]) {
        try { cb(event) } catch (e) { console.warn('[WS] Listener error:', e) }
      }
    }

    // Generic event types that components can listen to
    const routedEvents = [
      'foreshadows_updated',
      'relationships_updated',
      'timeline_updated',
      'token_update',
      'chapter_completed',
      'god_decision',
      'scene_simulated',
      'reflection_complete',
    ]
    // Already dispatched above via listeners dict
  }

  return { connected, connect, disconnect }
}
