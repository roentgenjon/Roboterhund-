import React, { useEffect, useRef, useState } from 'react'
import { createStatusWS, startMapping, saveMap, stopRobot, ApiError } from '../api'
import type { RobotStatus } from '../api'

function StatusBadge({ mode }: { mode: string }) {
  const color =
    mode === 'mapping'    ? 'bg-yellow-500' :
    mode === 'navigating' ? 'bg-green-500'  :
    mode === 'idle'       ? 'bg-gray-500'   : 'bg-red-500'
  return (
    <span className={`inline-block w-2.5 h-2.5 rounded-full ${color} mr-2`} />
  )
}

export default function ControlPanel() {
  const [status, setStatus] = useState<RobotStatus | null>(null)
  const [wsOk, setWsOk] = useState(false)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = createStatusWS(
      (d) => { setStatus(d); setWsOk(true) },
      () => setWsOk(false),
    )
    ws.onclose = () => setWsOk(false)
    wsRef.current = ws
    return () => ws.close()
  }, [])

  const flash = (text: string, ok: boolean) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  const cmd = async (label: string, fn: () => Promise<void>) => {
    try {
      await fn()
      flash(`${label} erfolgreich`, true)
    } catch (e) {
      const err = e instanceof ApiError ? e.message : String(e)
      if (err.includes('501')) {
        flash(`${label}: Nur am echten Roboter verfügbar`, false)
      } else if (err.includes('401')) {
        flash('Falscher PIN', false)
      } else {
        flash(`Fehler: ${err}`, false)
      }
    }
  }

  return (
    <div className="p-4 max-w-lg mx-auto space-y-4">
      {/* Status */}
      <div className="bg-gray-900 rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Verbindung</span>
          <span className={`text-xs font-medium ${wsOk ? 'text-green-400' : 'text-red-400'}`}>
            {wsOk ? 'Verbunden' : 'Getrennt'}
          </span>
        </div>
        {status && (
          <>
            <div className="flex items-center">
              <StatusBadge mode={status.mode} />
              <span className="text-sm capitalize">{status.mode}</span>
            </div>
            {status.battery_percent !== null && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Akku</span>
                <span className={`text-sm font-medium ${status.battery_percent > 20 ? 'text-green-400' : 'text-red-400'}`}>
                  {status.battery_percent.toFixed(0)} %
                </span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Position</span>
              <span className="text-sm font-mono text-gray-300">
                x={status.position_x.toFixed(2)} y={status.position_y.toFixed(2)}
              </span>
            </div>
          </>
        )}
        {!status && !wsOk && (
          <p className="text-gray-500 text-sm">Kein Status-Signal empfangen</p>
        )}
      </div>

      {/* Feedback */}
      {msg && (
        <div className={`rounded-lg px-4 py-2 text-sm ${msg.ok ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
          {msg.text}
        </div>
      )}

      {/* Buttons */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => cmd('Mapping starten', startMapping)}
          className="bg-yellow-700 hover:bg-yellow-600 text-white rounded-xl py-4 font-medium text-sm transition"
        >
          Mapping starten
        </button>
        <button
          onClick={() => cmd('Karte speichern', saveMap)}
          className="bg-blue-700 hover:bg-blue-600 text-white rounded-xl py-4 font-medium text-sm transition"
        >
          Karte speichern
        </button>
        <button
          onClick={() => cmd('Stop', stopRobot)}
          className="col-span-2 bg-red-700 hover:bg-red-600 text-white rounded-xl py-5 font-bold text-lg transition"
        >
          STOP
        </button>
      </div>

      <p className="text-xs text-gray-600 text-center">
        Für autonome Navigation → Tab Karte, dann Klick auf Ziel-Position
      </p>
    </div>
  )
}
