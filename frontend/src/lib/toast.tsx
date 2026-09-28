import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'

type Toast = { id: number; kind: 'success' | 'error' | 'info'; text: string }
let listeners: ((t: Toast[]) => void)[] = []
let toasts: Toast[] = []
let nextId = 1

function emit() {
  listeners.forEach((l) => l(toasts))
}
function dismiss(id: number) {
  toasts = toasts.filter((x) => x.id !== id)
  emit()
}
function push(kind: Toast['kind'], text: string) {
  const t = { id: nextId++, kind, text }
  toasts = [...toasts, t].slice(-4)
  emit()
  setTimeout(() => dismiss(t.id), kind === 'error' ? 8000 : 4000)
}

export const toast = {
  success: (text: string) => push('success', text),
  error: (text: string) => push('error', text),
  info: (text: string) => push('info', text),
}

const ICON = { success: CheckCircle2, error: AlertCircle, info: Info }

export function Toaster() {
  const [items, setItems] = useState<Toast[]>(toasts)
  useEffect(() => {
    listeners.push(setItems)
    return () => {
      listeners = listeners.filter((l) => l !== setItems)
    }
  }, [])
  return (
    <div className="toaster" role="status" aria-live="polite">
      {items.map((t) => {
        const Icon = ICON[t.kind]
        return (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <Icon size={17} aria-hidden />
            <div className="grow">{t.text}</div>
            <button className="icon-btn" style={{ padding: 2, marginTop: -1 }} onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
