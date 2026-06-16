/**
 * api.ts – Typed wrappers around all backend endpoints.
 *
 * The base URL is auto-detected: in development Vite proxies /api → localhost:8000;
 * in production the frontend is served by the same backend so relative paths work.
 */

const BASE = ''  // relative – works in both dev (via Vite proxy) and prod

export interface MapData {
  png_b64: string
  width: number
  height: number
  resolution: number
  origin_x: number
  origin_y: number
  stamp: number
}

export interface RobotStatus {
  mode: string
  battery_percent: number | null
  position_x: number
  position_y: number
  yaw_deg: number
  stamp: number
}

export interface Zone {
  name: string
  points: [number, number][]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _pin = ''
export function setPin(pin: string) { _pin = pin }
export function getPin() { return _pin }

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json', ...extra }
  if (_pin) h['X-Pin'] = _pin
  return h
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, { ...init, headers: headers(init?.headers as Record<string, string> ?? {}) })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json() as Promise<T>
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export async function fetchHealth(): Promise<{ status: string; mock: boolean; pin_enabled: boolean }> {
  return apiFetch('/api/health')
}

export async function fetchMap(): Promise<MapData> {
  return apiFetch('/api/map')
}

export async function fetchStatus(): Promise<RobotStatus> {
  return apiFetch('/api/status')
}

export async function fetchZones(): Promise<{ zones: Zone[] }> {
  return apiFetch('/api/zones')
}

export async function saveZones(zones: Zone[]): Promise<{ status: string; count: number }> {
  return apiFetch('/api/zones', { method: 'POST', body: JSON.stringify({ zones }) })
}

export async function startMapping(): Promise<void> {
  await apiFetch('/api/control/mapping/start', { method: 'POST' })
}

export async function saveMap(mapName = 'go2_map'): Promise<void> {
  await apiFetch(`/api/control/mapping/save?map_name=${encodeURIComponent(mapName)}`, { method: 'POST' })
}

export async function navigateTo(x: number, y: number, yaw_deg = 0): Promise<void> {
  await apiFetch('/api/control/navigate', { method: 'POST', body: JSON.stringify({ x, y, yaw_deg }) })
}

export async function stopRobot(): Promise<void> {
  await apiFetch('/api/control/stop', { method: 'POST' })
}

export async function sendChat(message: string): Promise<{ answer: string }> {
  return apiFetch('/api/chat', { method: 'POST', body: JSON.stringify({ message }) })
}

export async function setOpenAIKey(key: string): Promise<void> {
  await apiFetch('/api/settings/openai-key', { method: 'POST', body: JSON.stringify({ key }) })
}

// ---------------------------------------------------------------------------
// WebSocket factory
// ---------------------------------------------------------------------------

export function createMapWS(onMessage: (data: MapData) => void, onError: (e: Event) => void): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${protocol}://${location.host}/ws/map`)
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch { /* ignore parse errors */ }
  }
  ws.onerror = onError
  return ws
}

export function createStatusWS(onMessage: (data: RobotStatus) => void, onError: (e: Event) => void): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${protocol}://${location.host}/ws/status`)
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch { /* ignore parse errors */ }
  }
  ws.onerror = onError
  return ws
}
