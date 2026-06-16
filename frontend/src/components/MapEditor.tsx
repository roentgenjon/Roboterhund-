import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createMapWS, fetchZones, saveZones, navigateTo, ApiError } from '../api'
import type { MapData, Zone } from '../api'

type Tool = 'navigate' | 'zone'

interface Point { x: number; y: number }

export default function MapEditor() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [mapData, setMapData] = useState<MapData | null>(null)
  const [zones, setZones] = useState<Zone[]>([])
  const [draft, setDraft] = useState<Point[]>([])
  const [tool, setTool] = useState<Tool>('navigate')
  const [zoneName, setZoneName] = useState('Zone 1')
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  const flash = (text: string, ok: boolean) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 3000)
  }

  // Load saved zones on mount
  useEffect(() => {
    fetchZones().then(({ zones: z }) => setZones(z)).catch(() => {})
  }, [])

  // Live map via WebSocket
  useEffect(() => {
    const ws = createMapWS(
      (d) => setMapData(d),
      () => {},
    )
    wsRef.current = ws
    return () => ws.close()
  }, [])

  // Redraw canvas whenever map or zones change
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !mapData) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { png_b64, width, height } = mapData
    canvas.width = width
    canvas.height = height

    const img = new Image()
    img.onload = () => {
      ctx.drawImage(img, 0, 0)
      // Draw saved zones
      zones.forEach((z, idx) => {
        if (z.points.length < 2) return
        ctx.beginPath()
        const colors = ['rgba(239,68,68,0.4)', 'rgba(59,130,246,0.4)', 'rgba(234,179,8,0.4)', 'rgba(34,197,94,0.4)']
        ctx.fillStyle = colors[idx % colors.length]
        ctx.strokeStyle = colors[idx % colors.length].replace('0.4', '1')
        ctx.lineWidth = 2
        const [[fx, fy], ...rest] = z.points.map(([mx, my]) => metreToCanvas(mx, my, mapData))
        ctx.moveTo(fx, fy)
        rest.forEach(([cx, cy]) => ctx.lineTo(cx, cy))
        ctx.closePath()
        ctx.fill()
        ctx.stroke()
        // Label
        if (z.points.length > 0) {
          const cx = z.points.reduce((s, p) => s + p[0], 0) / z.points.length
          const cy = z.points.reduce((s, p) => s + p[1], 0) / z.points.length
          const [lx, ly] = metreToCanvas(cx, cy, mapData)
          ctx.fillStyle = 'white'
          ctx.font = '10px sans-serif'
          ctx.fillText(z.name, lx - 20, ly)
        }
      })
      // Draw draft polygon
      if (draft.length > 0) {
        ctx.beginPath()
        ctx.strokeStyle = 'rgba(251,146,60,0.9)'
        ctx.lineWidth = 2
        ctx.setLineDash([5, 3])
        ctx.moveTo(draft[0].x, draft[0].y)
        draft.slice(1).forEach((p) => ctx.lineTo(p.x, p.y))
        ctx.stroke()
        ctx.setLineDash([])
        draft.forEach((p) => {
          ctx.beginPath()
          ctx.arc(p.x, p.y, 4, 0, Math.PI * 2)
          ctx.fillStyle = 'orange'
          ctx.fill()
        })
      }
    }
    img.src = `data:image/png;base64,${png_b64}`
    imgRef.current = img
  }, [mapData, zones, draft])

  // Convert map pixel coords to metres using map metadata
  function canvasToMetre(cx: number, cy: number, md: MapData): [number, number] {
    const mx = md.origin_x + cx * md.resolution
    const my = md.origin_y + (md.height - cy) * md.resolution
    return [mx, my]
  }

  function metreToCanvas(mx: number, my: number, md: MapData): [number, number] {
    const cx = (mx - md.origin_x) / md.resolution
    const cy = md.height - (my - md.origin_y) / md.resolution
    return [cx, cy]
  }

  const getCanvasPoint = (e: React.MouseEvent<HTMLCanvasElement>): Point => {
    const rect = canvasRef.current!.getBoundingClientRect()
    const scaleX = (canvasRef.current!.width)  / rect.width
    const scaleY = (canvasRef.current!.height) / rect.height
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top)  * scaleY,
    }
  }

  const handleCanvasClick = async (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!mapData) return
    const pt = getCanvasPoint(e)

    if (tool === 'navigate') {
      const [mx, my] = canvasToMetre(pt.x, pt.y, mapData)
      try {
        await navigateTo(mx, my)
        flash(`Navigiere zu (${mx.toFixed(2)}, ${my.toFixed(2)})`, true)
      } catch (err) {
        const detail = err instanceof ApiError ? err.message : String(err)
        if (detail.includes('501')) {
          flash('Navigation: nur am echten Roboter verfügbar', false)
        } else {
          flash(`Fehler: ${detail}`, false)
        }
      }
      return
    }

    // Zone-drawing tool: single click adds a point
    setDraft((d) => [...d, pt])
  }

  const handleCanvasDblClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    if (tool !== 'zone' || draft.length < 3 || !mapData) return
    // Close the polygon and add zone
    const points: [number, number][] = draft.map((p) => canvasToMetre(p.x, p.y, mapData))
    const newZone: Zone = { name: zoneName, points }
    setZones((z) => [...z, newZone])
    setDraft([])
    setZoneName(`Zone ${zones.length + 2}`)
  }

  const handleSaveZones = async () => {
    try {
      await saveZones(zones)
      flash(`${zones.length} Zone(n) gespeichert & angewendet`, true)
    } catch (err) {
      flash(`Fehler: ${err instanceof ApiError ? err.message : String(err)}`, false)
    }
  }

  const deleteZone = (idx: number) => {
    setZones((z) => z.filter((_, i) => i !== idx))
  }

  return (
    <div className="flex flex-col lg:flex-row h-full gap-0">
      {/* Map canvas */}
      <div className="flex-1 relative bg-black overflow-auto">
        {!mapData && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500 animate-pulse">
            Warte auf Karte…
          </div>
        )}
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          onDoubleClick={handleCanvasDblClick}
          style={{ imageRendering: 'pixelated', maxWidth: '100%', cursor: tool === 'navigate' ? 'crosshair' : 'cell' }}
          className="block"
        />
      </div>

      {/* Sidebar */}
      <div className="lg:w-64 bg-gray-900 border-l border-gray-800 p-4 space-y-4 shrink-0">
        {msg && (
          <div className={`rounded-lg px-3 py-2 text-xs ${msg.ok ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
            {msg.text}
          </div>
        )}

        {/* Tool selector */}
        <div>
          <p className="text-xs text-gray-400 mb-2">Werkzeug</p>
          <div className="grid grid-cols-2 gap-2">
            {(['navigate', 'zone'] as Tool[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTool(t); setDraft([]) }}
                className={`text-xs py-2 rounded-lg font-medium transition
                  ${tool === t ? 'bg-brand-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'}`}
              >
                {t === 'navigate' ? '🎯 Navigation' : '✏️ Zone zeichnen'}
              </button>
            ))}
          </div>
        </div>

        {/* Zone-drawing controls */}
        {tool === 'zone' && (
          <div className="space-y-2">
            <label className="text-xs text-gray-400">Zonenname</label>
            <input
              value={zoneName}
              onChange={(e) => setZoneName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white"
            />
            {draft.length > 0 && (
              <p className="text-xs text-orange-400">
                {draft.length} Punkt(e) – Doppelklick zum Schließen (min. 3)
              </p>
            )}
            {draft.length > 0 && (
              <button
                onClick={() => setDraft([])}
                className="w-full text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded py-1"
              >
                Abbrechen
              </button>
            )}
          </div>
        )}

        {/* Zone list */}
        <div>
          <p className="text-xs text-gray-400 mb-1">Zonen ({zones.length})</p>
          {zones.length === 0 && (
            <p className="text-xs text-gray-600">Keine Zonen definiert</p>
          )}
          <ul className="space-y-1">
            {zones.map((z, i) => (
              <li key={i} className="flex items-center justify-between bg-gray-800 rounded px-2 py-1">
                <span className="text-xs text-gray-200 truncate">{z.name}</span>
                <button
                  onClick={() => deleteZone(i)}
                  className="text-red-500 hover:text-red-400 text-xs ml-1 shrink-0"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Save */}
        <button
          onClick={handleSaveZones}
          className="w-full bg-green-700 hover:bg-green-600 text-white rounded-lg py-2 text-sm font-medium transition"
        >
          Speichern & Anwenden
        </button>

        <p className="text-xs text-gray-600">
          Einzel-Klick: Punkt setzen<br />
          Doppelklick: Polygon schließen<br />
          Navigation: Klick = Fahrziel
        </p>
      </div>
    </div>
  )
}
