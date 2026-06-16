import React, { useRef, useState } from 'react'
import { sendChat, ApiError } from '../api'

interface Message {
  role: 'user' | 'bot' | 'error'
  text: string
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Hallo! Ich bin Robo, dein Roboterhund-Assistent. Was möchtest du wissen?' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text }])
    setLoading(true)
    scrollToBottom()

    try {
      const { answer } = await sendChat(text)
      setMessages((m) => [...m, { role: 'bot', text: answer }])
    } catch (e) {
      let errText = 'Unbekannter Fehler'
      if (e instanceof ApiError) {
        if (e.status === 400) {
          errText = 'Kein OpenAI-Key gesetzt. Bitte in den Einstellungen eingeben.'
        } else if (e.status === 503) {
          errText = 'Keine Internetverbindung für ChatGPT erreichbar. Mapping und Navigation funktionieren trotzdem weiter.'
        } else {
          errText = e.message
        }
      }
      setMessages((m) => [...m, { role: 'error', text: errText }])
    }

    setLoading(false)
    scrollToBottom()
  }

  return (
    <div className="flex flex-col h-full max-h-screen">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-xs lg:max-w-md rounded-2xl px-4 py-2 text-sm leading-relaxed
                ${m.role === 'user'  ? 'bg-brand-600 text-white'
                : m.role === 'error' ? 'bg-red-900/60 text-red-300 border border-red-700'
                : 'bg-gray-800 text-gray-100'}`}
            >
              {m.role === 'bot' && <span className="mr-1">🐕</span>}
              {m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 text-gray-400 rounded-2xl px-4 py-2 text-sm animate-pulse">
              🐕 denkt…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 bg-gray-900 p-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Frag Robo etwas…"
          disabled={loading}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white rounded-xl px-4 py-2 text-sm font-medium transition"
        >
          Senden
        </button>
      </div>
    </div>
  )
}
