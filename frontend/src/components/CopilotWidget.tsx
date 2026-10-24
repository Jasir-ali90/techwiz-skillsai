import { useState, useRef, useEffect } from 'react'
import { Bot, X, Send, Sparkles, BookOpen, ArrowRight } from 'lucide-react'
import { copilot } from '../api/endpoints'
import { Spinner } from './ui'

type Citation = {
  document_code: string
  title: string
  section_id: string | null
  chunk_code: string
  similarity: number
}

type Message = {
  id: string
  sender: 'user' | 'assistant'
  text: string
  citations?: Citation[]
  confidence?: number
  grounded?: boolean
  followups?: string[]
}

const DEFAULT_QUESTIONS = [
  'What are the mandatory security training deadlines?',
  'What is the session inactivity timeout under POL-INFOSEC-001?',
  'How do code reviews and Git commit messages work?',
  'What is the company leave policy?',
]

export function CopilotWidget() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "Hello! I am **Nexora Copilot**, your verifiable AI onboarding mentor. Ask me anything about company policies, SOPs, security obligations, or role responsibilities. Every answer I provide is cited directly from verified company documents.",
      followups: DEFAULT_QUESTIONS,
    },
  ])

  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, open])

  async function handleSend(queryText?: string) {
    const q = (queryText || input).trim()
    if (!q || loading) return

    const userMsg: Message = { id: `u-${Date.now()}`, sender: 'user', text: q }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res: any = await copilot.ask({ question: q })
      const aiMsg: Message = {
        id: `a-${Date.now()}`,
        sender: 'assistant',
        text: res.answer || 'No answer returned.',
        citations: res.citations || [],
        confidence: res.confidence_score,
        grounded: res.grounded !== false,
        followups: res.suggested_followups || [],
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: `⚠️ I encountered an error retrieving policy data: ${err?.message || 'Server error'}. Please try again shortly.`,
          grounded: false,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Floating Action Button */}
      <div style={{ position: 'fixed', right: 28, bottom: 28, zIndex: 45 }}>
        <button
          onClick={() => setOpen(!open)}
          title="Open Nexora AI Copilot"
          style={{
            width: 54,
            height: 54,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #0ea5e9 0%, #6366f1 100%)',
            border: '2px solid rgba(255, 255, 255, 0.25)',
            color: '#fff',
            display: 'grid',
            placeItems: 'center',
            cursor: 'pointer',
            boxShadow: '0 8px 25px rgba(14, 165, 233, 0.45), 0 0 15px rgba(99, 102, 241, 0.35)',
            transition: 'transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08) translateY(-2px)')}
          onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1) translateY(0)')}
        >
          {open ? <X size={24} /> : <Sparkles size={24} />}
        </button>
      </div>

      {/* Floating Chat Modal */}
      {open && (
        <div
          style={{
            position: 'fixed',
            right: 28,
            bottom: 92,
            width: 'min(420px, calc(100vw - 36px))',
            height: 'min(620px, calc(100vh - 120px))',
            background: 'var(--surface)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid var(--border-strong)',
            borderRadius: 18,
            boxShadow: 'var(--shadow-lg), 0 0 35px rgba(14, 165, 233, 0.2)',
            zIndex: 45,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'pop 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '16px 18px',
              borderBottom: '1px solid var(--border)',
              background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.12) 0%, rgba(99, 102, 241, 0.08) 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, #0ea5e9, #6366f1)',
                  display: 'grid',
                  placeItems: 'center',
                  color: '#fff',
                }}
              >
                <Bot size={18} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                  Nexora Copilot
                  <span className="badge badge-good" style={{ fontSize: 10, padding: '1px 6px' }}>
                    Zero Hallucination
                  </span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--text-3)' }}>Verified Onboarding Intelligence</div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              style={{ background: 'none', border: 0, color: 'var(--text-3)', cursor: 'pointer', padding: 4 }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Chat Messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '88%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
              >
                <div
                  style={{
                    padding: '11px 14px',
                    borderRadius: 13,
                    fontSize: 13,
                    lineHeight: 1.55,
                    background:
                      m.sender === 'user'
                        ? 'linear-gradient(135deg, #2563eb, #0284c7)'
                        : 'var(--surface-2)',
                    color: m.sender === 'user' ? '#fff' : 'var(--text)',
                    border: m.sender === 'user' ? 'none' : '1px solid var(--border)',
                    boxShadow: 'var(--shadow-sm)',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {m.text}
                </div>

                {/* Citations & Evidence Pill */}
                {m.citations && m.citations.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, paddingLeft: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <BookOpen size={12} /> Sources:
                    </span>
                    {m.citations.map((c, i) => (
                      <span
                        key={i}
                        className="badge badge-info"
                        style={{ fontSize: 10.5, padding: '1px 7px' }}
                        title={`${c.title} (Match: ${Math.round(c.similarity * 100)}%)`}
                      >
                        {c.document_code} §{c.section_id || 'Gen'}
                      </span>
                    ))}
                  </div>
                )}

                {/* Suggested follow-ups */}
                {m.followups && m.followups.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Suggested Questions:</span>
                    {m.followups.map((f, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(f)}
                        style={{
                          textAlign: 'left',
                          fontSize: 11.5,
                          padding: '6px 10px',
                          borderRadius: 8,
                          background: 'var(--surface-2)',
                          border: '1px solid var(--border)',
                          color: 'var(--accent-text)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 6,
                          transition: 'background 0.12s ease',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-3)')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface-2)')}
                      >
                        <span>{f}</span>
                        <ArrowRight size={12} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-3)', fontSize: 12.5, padding: '4px 8px' }}>
                <Spinner label="" /> Nexora Copilot searching verified policies…
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input Box */}
          <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              style={{ display: 'flex', gap: 8 }}
            >
              <input
                className="input"
                placeholder="Ask about rules, policies, or procedures…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                style={{ fontSize: 13, height: 38 }}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={!input.trim() || loading}
                style={{ height: 38, padding: '0 12px' }}
                title="Send inquiry"
              >
                <Send size={15} />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
