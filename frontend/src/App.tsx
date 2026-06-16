import React, { useEffect, useState } from 'react'
import { fetchHealth, setPin, ApiError } from './api'
import ConnectionPage from './components/ConnectionPage'
import Dashboard from './components/Dashboard'

type AppState = 'connecting' | 'pin-required' | 'connected' | 'error'

export default function App() {
  const [appState, setAppState] = useState<AppState>('connecting')
  const [pinEnabled, setPinEnabled] = useState(false)
  const [error, setError] = useState('')

  const attemptConnect = async (pin = '') => {
    setPin(pin)
    setAppState('connecting')
    setError('')
    try {
      const health = await fetchHealth()
      if (health.pin_enabled && !pin) {
        setPinEnabled(true)
        setAppState('pin-required')
      } else {
        setAppState('connected')
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setPinEnabled(true)
        setAppState('pin-required')
        setError('Falscher PIN – bitte nochmal versuchen.')
      } else {
        setError('Backend nicht erreichbar. Stelle sicher, dass du mit dem Hunde-WLAN verbunden bist und das Backend läuft.')
        setAppState('error')
      }
    }
  }

  useEffect(() => { attemptConnect() }, [])

  if (appState === 'connected') {
    return <Dashboard pinEnabled={pinEnabled} />
  }

  return (
    <ConnectionPage
      state={appState}
      error={error}
      onConnect={attemptConnect}
    />
  )
}
