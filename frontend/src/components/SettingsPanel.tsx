import React, { useState } from 'react'
import { setOpenAIKey, ApiError } from '../api'

export default function SettingsPanel() {
  const [key, setKey] = useState('')
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [saving, setSaving] = useState(false)

  const flash = (text: string, ok: boolean) => {
    setMsg({ text, ok })
    setTimeout(() => setMsg(null), 4000)
  }

  const handleSave = async () => {
    if (!key.trim()) return
    setSaving(true)
    try {
      await setOpenAIKey(key.trim())
      flash('OpenAI-Key gesetzt (nur im Arbeitsspeicher, wird nicht gespeichert)', true)
      setKey('')
    } catch (e) {
      flash(`Fehler: ${e instanceof ApiError ? e.message : String(e)}`, false)
    }
    setSaving(false)
  }

  const handleClear = async () => {
    setSaving(true)
    try {
      await setOpenAIKey('')
      flash('OpenAI-Key geleert', true)
      setKey('')
    } catch {
      // ignore
    }
    setSaving(false)
  }

  return (
    <div className="p-4 max-w-lg mx-auto space-y-6">
      <div className="bg-gray-900 rounded-xl p-5 space-y-4">
        <h2 className="text-lg font-semibold text-white">Chat-Einstellungen</h2>

        <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3 text-xs text-yellow-300">
          Der OpenAI-Key wird <strong>nur im Arbeitsspeicher</strong> des Backends
          gehalten. Er wird nicht auf die Festplatte geschrieben und nicht in
          Logs oder API-Antworten ausgegeben. Er geht verloren, wenn das Backend
          neu gestartet wird.
        </div>

        {msg && (
          <div className={`rounded-lg px-3 py-2 text-sm ${msg.ok ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
            {msg.text}
          </div>
        )}

        <div className="space-y-2">
          <label className="block text-sm text-gray-400">OpenAI API-Key</label>
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="sk-…"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving || !key.trim()}
            className="flex-1 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white rounded-lg py-2 text-sm font-medium transition"
          >
            {saving ? 'Speichert…' : 'Key setzen'}
          </button>
          <button
            onClick={handleClear}
            disabled={saving}
            className="bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg py-2 px-4 text-sm transition"
          >
            Löschen
          </button>
        </div>
      </div>

      <div className="bg-gray-900 rounded-xl p-5 space-y-3">
        <h2 className="text-lg font-semibold text-white">Netzwerk-Info</h2>
        <p className="text-sm text-gray-400">
          Das Dashboard läuft vollständig im lokalen Hunde-WLAN. Internet wird
          <strong> nur für den Chat</strong> benötigt (OpenAI). Alle anderen
          Funktionen (Karte, Navigation, Zonen) sind offline verfügbar.
        </p>
        <p className="text-sm text-gray-400">
          Falls der Chat nicht funktioniert: überprüfe ob der Service-Rechner
          eine zweite Internetverbindung hat (Ethernet oder Mobilfunk).
        </p>
        <div className="border border-gray-700 rounded-lg p-3 space-y-1 text-xs text-gray-500 font-mono">
          <div>Backend-URL: <span className="text-gray-300">{location.host}</span></div>
          <div>Protokoll: <span className="text-gray-300">{location.protocol}</span></div>
        </div>
      </div>
    </div>
  )
}
