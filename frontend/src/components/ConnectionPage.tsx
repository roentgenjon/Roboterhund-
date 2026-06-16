import React, { useState } from 'react'

interface Props {
  state: 'connecting' | 'pin-required' | 'error'
  error: string
  onConnect: (pin: string) => void
}

export default function ConnectionPage({ state, error, onConnect }: Props) {
  const [pin, setPin] = useState('')

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="w-full max-w-sm bg-gray-900 rounded-2xl shadow-2xl p-8 space-y-6">
        <div className="text-center">
          <div className="text-5xl mb-3">🐕</div>
          <h1 className="text-2xl font-bold text-white">Go2 Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Unitree Go2 Roboterhund</p>
        </div>

        {state === 'connecting' && (
          <div className="text-center text-gray-400 animate-pulse">
            Verbinde mit Backend…
          </div>
        )}

        {state === 'error' && (
          <div className="space-y-4">
            <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
              {error}
            </div>
            <button
              onClick={() => onConnect('')}
              className="w-full bg-brand-600 hover:bg-brand-700 text-white rounded-lg py-2 font-medium transition"
            >
              Erneut verbinden
            </button>
          </div>
        )}

        {state === 'pin-required' && (
          <form
            onSubmit={(e) => { e.preventDefault(); onConnect(pin) }}
            className="space-y-4"
          >
            {error && (
              <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
                {error}
              </div>
            )}
            <div>
              <label className="block text-sm text-gray-400 mb-1">PIN eingeben</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="****"
                autoFocus
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-brand-600 hover:bg-brand-700 text-white rounded-lg py-2 font-medium transition"
            >
              Anmelden
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
