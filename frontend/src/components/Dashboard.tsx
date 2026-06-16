import React, { useState } from 'react'
import MapEditor from './MapEditor'
import ControlPanel from './ControlPanel'
import ChatPanel from './ChatPanel'
import SettingsPanel from './SettingsPanel'

type Tab = 'map' | 'control' | 'chat' | 'settings'

interface Props {
  pinEnabled: boolean
}

export default function Dashboard({ pinEnabled }: Props) {
  const [tab, setTab] = useState<Tab>('control')

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'control', label: 'Steuerung', icon: '🕹️' },
    { id: 'map',     label: 'Karte',     icon: '🗺️' },
    { id: 'chat',    label: 'Chat',      icon: '💬' },
    { id: 'settings',label: 'Settings',  icon: '⚙️' },
  ]

  return (
    <div className="min-h-screen flex flex-col bg-gray-950">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center gap-3">
        <span className="text-2xl">🐕</span>
        <h1 className="text-lg font-bold text-white">Go2 Dashboard</h1>
        <span className="ml-auto text-xs text-gray-500">lokal · offline</span>
      </header>

      {/* Tab bar */}
      <nav className="bg-gray-900 border-b border-gray-800 flex">
        {tabs.map(({ id, label, icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 py-3 text-sm font-medium flex flex-col items-center gap-0.5 transition
              ${tab === id
                ? 'text-brand-500 border-b-2 border-brand-500'
                : 'text-gray-400 hover:text-gray-200'
              }`}
          >
            <span className="text-base">{icon}</span>
            <span className="hidden sm:block">{label}</span>
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="flex-1 overflow-auto">
        {tab === 'control'  && <ControlPanel />}
        {tab === 'map'      && <MapEditor />}
        {tab === 'chat'     && <ChatPanel />}
        {tab === 'settings' && <SettingsPanel />}
      </main>
    </div>
  )
}
