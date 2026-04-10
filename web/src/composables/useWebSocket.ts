import { ref } from 'vue'
import { useProgressStore } from '@/stores/progress'
import { useLiveWritingStore } from '@/stores/liveWriting'
import { useEventLogStore } from '@/stores/eventLog'
import { useLiveMonitorStore } from '@/stores/liveMonitor'

let ws: WebSocket | null = null
const connected = ref(false)

// Exponential backoff for reconnection
let _reconnectAttempts = 0
const _BASE_RECONNECT_MS = 1000
const _MAX_RECONNECT_MS = 30000

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
      _reconnectAttempts = 0 // reset on successful connect
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
      // Exponential backoff reconnection
      const delay = Math.min(_BASE_RECONNECT_MS * 2 ** _reconnectAttempts, _MAX_RECONNECT_MS)
      _reconnectAttempts++
      setTimeout(() => connect(), delay)
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
    const eventLogStore = useEventLogStore()
    const monitorStore = useLiveMonitorStore()

    // Route events to appropriate stores
    if (event.type === 'progress' || event.type === 'progress_update') {
      progressStore.updateFromWS(event)
    }

    // V9: Route simulation progress events
    if (event.type === 'simulation_progress') {
      progressStore.updateSimFromWS(event)
      monitorStore.handleSimulationProgress(event)
    }

    // V9: Route decoupled pipeline events directly to monitor store
    if (event.type === 'preparation_started') monitorStore.handlePreparationStarted()
    if (event.type === 'preparation_finished') monitorStore.handlePreparationFinished(event)
    if (event.type === 'simulation_started') monitorStore.handleSimulationStarted(event)
    if (event.type === 'simulation_finished') monitorStore.handleSimulationFinished(event)
    if (event.type === 'beat_simulated') monitorStore.handleBeatSimulated(event)
    if (event.type === 'beat_plan_completed') monitorStore.handleBeatPlanCompleted(event)
    if (event.type === 'beats_picked') monitorStore.currentPhase = 'simulating'

    // All events go to live writing for real-time display
    liveWritingStore.handleEvent(event)

    // All events go to event log for the sidebar / overview log
    eventLogStore.pushFromWS(event)

    // Route to component-level listeners
    const eventType = event.type as string
    if (eventType && listeners[eventType]) {
      for (const cb of listeners[eventType]) {
        try { cb(event) } catch (e) { console.warn('[WS] Listener error:', e) }
      }
    }
  }

  return { connected, connect, disconnect }
}
