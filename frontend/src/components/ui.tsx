import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, AlertTriangle, ArrowLeft, Check, CheckCircle2, ChevronDown, ChevronRight, Info, Inbox, X, type LucideIcon } from 'lucide-react'
import type { ApiError, Json } from '../api/client'

// ------------------------------------------------------------ primitives
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: LucideIcon
  block?: boolean
}
export function Button({ variant = 'secondary', size = 'md', loading, icon: Icon, block, children, disabled, className = '', ...rest }: BtnProps) {
  const iconSize = size === 'sm' ? 14 : 16
  return (
    <button className={`btn btn-${variant} btn-${size} ${block ? 'btn-block' : ''} ${className}`} disabled={disabled || loading} {...rest}>
      {loading ? <span className="spinner spinner-sm" aria-hidden /> : Icon && <Icon size={iconSize} aria-hidden />}
      {children}
    </button>
  )
}

export function Card({ title, subtitle, icon: Icon, actions, children, className = '' }: {
  title?: ReactNode
  subtitle?: ReactNode
  icon?: LucideIcon
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <div className="card-title">
            {Icon && <Icon size={18} aria-hidden />}
            <div>
              {title && <h3>{title}</h3>}
              {subtitle && <div className="card-sub">{subtitle}</div>}
            </div>
          </div>
          {actions && <div className="row gap-sm wrap">{actions}</div>}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  )
}

/** A small "View all ›" style link for card headers. */
export const CardLink = ({ to, children }: { to: string; children: ReactNode }) => (
  <Link className="card-link" to={to}>
    {children} <ChevronRight size={14} aria-hidden />
  </Link>
)

export function PageHeader({ title, subtitle, actions, back }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; back?: { to: string; label: string } }) {
  return (
    <div className="page-head">
      <div>
        {back && (
          <Link className="back-link" to={back.to}>
            <ArrowLeft size={14} aria-hidden /> {back.label}
          </Link>
        )}
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="row gap-sm wrap">{actions}</div>}
    </div>
  )
}

export const Spinner = ({ label }: { label?: string }) => (
  <div className="center muted pad" role="status">
    <span className="spinner" aria-hidden /> {label ?? 'Loading…'}
  </div>
)

export function Empty({ children, title, icon: Icon = Inbox, action }: { children?: ReactNode; title?: ReactNode; icon?: LucideIcon; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={20} aria-hidden />
      </div>
      {title && <div className="empty-title">{title}</div>}
      {children && <div className="small">{children}</div>}
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: ApiError | null | undefined; onRetry?: () => void }) {
  if (!error) return null
  return (
    <Alert kind="error">
      <div className="row between gap-sm wrap">
        <span>
          <strong>Something went wrong.</strong> {error.message}
        </span>
        {onRetry && (
          <Button size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </Alert>
  )
}

const ALERT_ICON = { info: Info, warn: AlertTriangle, error: AlertCircle, success: CheckCircle2 }
export function Alert({ kind = 'info', children }: { kind?: 'info' | 'warn' | 'error' | 'success'; children: ReactNode }) {
  const Icon = ALERT_ICON[kind]
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : undefined}>
      <Icon size={16} aria-hidden />
      <div className="alert-body">{children}</div>
    </div>
  )
}

// ------------------------------------------------------------ status
const TONE: Record<string, string> = {
  VERIFIED: 'good', VERIFIED_WITH_WARNING: 'warn', PARTIALLY_VERIFIED: 'warn', INCOMPLETE: 'bad',
  UNSUPPORTED: 'bad', CONTRADICTORY: 'bad', MANUAL_REVIEW_REQUIRED: 'warn', SOURCE_SUPPORT_MISSING: 'bad',
  REQUIREMENT_MISSING: 'bad', UNSUPPORTED_REQUIREMENT: 'bad', OUTDATED_SOURCE: 'bad', CONTRADICTION_DETECTED: 'bad',
  ACTIVE: 'good', OBSOLETE: 'muted', EXPIRED: 'muted', QUARANTINED: 'bad',
  CRITICAL: 'bad', ERROR: 'bad', WARNING: 'warn', INFO: 'info', HIGH: 'warn', MEDIUM: 'info', LOW: 'muted',
  COMPLETED: 'good', IN_PROGRESS: 'info', NOT_STARTED: 'muted', ON_TRACK: 'good', REQUIRES_ATTENTION: 'warn',
  BEHIND_SCHEDULE: 'bad', ASSESSMENT_REQUIRED: 'warn', OPEN: 'warn', APPROVED: 'good', REJECTED: 'bad',
  EDITED: 'info', REGENERATED: 'info', SUCCEEDED: 'good', FAILED: 'bad', RUNNING: 'info', PENDING: 'muted',
  MATCH: 'good', MISMATCH: 'warn', GENERATED: 'info', VALIDATED: 'info', SUPERSEDED: 'muted',
  SECTION_CHANGED: 'bad', VERSION_SUPERSEDED: 'warn', DOCUMENT_OBSOLETE: 'bad', FLAGGED_OUTDATED: 'warn',
  MANDATORY: 'warn', OPTIONAL: 'muted', PASSED: 'good', true: 'good', false: 'muted',
}
/** Friendlier wording for the few codes whose literal reading is unclear. */
const LABEL: Record<string, string> = {
  MANUAL_REVIEW_REQUIRED: 'Needs review',
  VERIFIED_WITH_WARNING: 'Verified, with warnings',
  REQUIRES_ATTENTION: 'Needs attention',
  ASSESSMENT_REQUIRED: 'Assessment due',
  VALIDATED: 'Checked',
  anthropic: 'Claude (Anthropic)',
  gemini: 'Google Gemini',
  groq: 'Groq',
  openrouter: 'OpenRouter',
  ollama: 'Ollama (local)',
  offline: 'Built-in offline writer',
}
/** Turns `BEHIND_SCHEDULE` or `mandatory_coverage` into "Behind schedule"; leaves codes like POL-HR-003 alone. */
export function humanize(value: unknown): string {
  const s = String(value)
  if (LABEL[s]) return LABEL[s]
  if (/^[a-z]+$/.test(s)) return s.charAt(0).toUpperCase() + s.slice(1)
  if (/^[A-Z][A-Z0-9_ ]*$/.test(s) || /^[a-z]+(_[a-z0-9]+)+$/.test(s)) {
    const t = s.replace(/_/g, ' ').toLowerCase()
    return t.charAt(0).toUpperCase() + t.slice(1)
  }
  return s
}
export function Badge({ value, tone, plain }: { value: ReactNode; tone?: string; plain?: boolean }) {
  if (value === null || value === undefined || value === '') return <span className="subtle">—</span>
  const t = tone ?? TONE[String(value)] ?? 'neutral'
  return <span className={`badge badge-${t} ${plain ? 'badge-plain' : ''}`}>{humanize(value)}</span>
}

export function Stat({ label, value, hint, tone, icon: Icon }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string; icon?: LucideIcon }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ''}`}>
      <div className="stat-top">
        <div className="stat-label">{label}</div>
        {Icon && (
          <span className="stat-icon">
            <Icon size={16} aria-hidden />
          </span>
        )}
      </div>
      <div className="stat-value">{value ?? '—'}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function Meter({ value, max = 100, tone }: { value: number | null | undefined; max?: number; tone?: string }) {
  const p = Math.max(0, Math.min(100, ((value ?? 0) / max) * 100))
  const t = tone ?? (p >= 99.9 ? 'good' : p >= 70 ? 'warn' : 'bad')
  return (
    <div className="meter" role="progressbar" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`meter-fill meter-${t}`} style={{ width: `${p}%` }} />
    </div>
  )
}

/** Meter with the percentage beside it — the common table-cell pattern. */
export const MeterLabel = ({ value, tone }: { value: number | null | undefined; tone?: string }) => (
  <div className="row gap-sm" style={{ minWidth: 120 }}>
    <Meter value={value} tone={tone} />
    <span className="small nowrap" style={{ width: 42, textAlign: 'right' }}>{pct(value)}</span>
  </div>
)

export function ProgressRing({ value, size = 88, tone = 'accent' }: { value: number; size?: number; tone?: string }) {
  const stroke = 8
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const p = Math.max(0, Math.min(100, value || 0))
  return (
    <div className="progress-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--neutral-soft)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`var(--${tone})`} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c - (p / 100) * c} style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
      </svg>
      <span>{pct(value)}</span>
    </div>
  )
}

export const initials = (name?: string | null) =>
  (name ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('') || '?'

export const Avatar = ({ name, large }: { name?: string | null; large?: boolean }) => (
  <span className={`avatar ${large ? 'avatar-lg' : ''}`} aria-hidden>
    {initials(name)}
  </span>
)

// ------------------------------------------------------------ table
export type Column<T = Json> = { key: string; label: ReactNode; render?: (row: T) => ReactNode; width?: string; className?: string }
export function Table({ rows, columns, onRowClick, empty = 'Nothing here yet.', rowKey }: {
  rows: Json[] | undefined
  columns: Column[]
  onRowClick?: (row: Json) => void
  empty?: ReactNode
  rowKey?: (row: Json, i: number) => string
}) {
  if (!rows?.length) return <Empty>{empty}</Empty>
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ width: c.width }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={rowKey ? rowKey(row, i) : (row.id ?? i)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (e) => e.key === 'Enter' && onRowClick(row) : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              className={onRowClick ? 'clickable' : ''}
            >
              {columns.map((c) => (
                <td key={c.key} className={c.className}>
                  {c.render ? c.render(row) : formatCell(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function formatCell(v: unknown): ReactNode {
  if (v === null || v === undefined || v === '') return <span className="subtle">—</span>
  if (typeof v === 'boolean') return v ? <Check size={16} className="good" aria-label="yes" /> : <span className="subtle">—</span>
  if (typeof v === 'object') return <code className="small">{JSON.stringify(v).slice(0, 120)}</code>
  return String(v)
}

// ------------------------------------------------------------ overlays and layout helpers
export function Modal({ open, title, onClose, children, footer, wide }: { open: boolean; title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal onMouseDown={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  )
}

export type TabDef = { id: string; label: ReactNode; icon?: LucideIcon; count?: number | null }
export function Tabs({ tabs, active, onChange }: { tabs: TabDef[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={active === t.id} className={`tab ${active === t.id ? 'tab-active' : ''}`} onClick={() => onChange(t.id)}>
          {t.icon && <t.icon size={15} aria-hidden />}
          {t.label}
          {t.count !== undefined && t.count !== null && <span className="tab-count">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function KeyValue({ items }: { items: [ReactNode, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v], i) => (
        <div key={i} className="kv-row">
          <dt>{k}</dt>
          <dd>{v ?? <span className="subtle">—</span>}</dd>
        </div>
      ))}
    </dl>
  )
}

export function JsonView({ value, collapsed = false, label = 'technical details' }: { value: Json; collapsed?: boolean; label?: string }) {
  const [open, setOpen] = useState(!collapsed)
  return (
    <div className="json">
      <button className="link small" onClick={() => setOpen(!open)} aria-expanded={open}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} {open ? `Hide ${label}` : `Show ${label}`}
      </button>
      {open && <pre>{JSON.stringify(value, null, 2)}</pre>}
    </div>
  )
}

/** A textarea that edits JSON and only reports valid values. It is seeded from
 * `initial` and re-seeded only when `resetKey` changes, so typing is never reformatted. */
export function JsonEditor({ initial, resetKey, onChange, rows = 18 }: { initial: Json; resetKey?: unknown; onChange: (v: Json, valid: boolean) => void; rows?: number }) {
  const [text, setText] = useState(() => JSON.stringify(initial, null, 2))
  const [bad, setBad] = useState<string | null>(null)
  useEffect(() => {
    setText(JSON.stringify(initial, null, 2))
    setBad(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey])
  return (
    <div>
      <textarea
        className={`input mono ${bad ? 'input-bad' : ''}`}
        rows={rows}
        value={text}
        spellCheck={false}
        onChange={(e) => {
          setText(e.target.value)
          try {
            const parsed = JSON.parse(e.target.value)
            setBad(null)
            onChange(parsed, true)
          } catch (err) {
            setBad(String(err).replace(/^SyntaxError: /, ''))
            onChange(null, false)
          }
        }}
      />
      <div className={`field-hint ${bad ? 'bad' : ''}`} style={{ marginTop: 6 }}>
        {bad ? `Not valid JSON yet: ${bad}` : 'Valid JSON'}
      </div>
    </div>
  )
}

export const fmtDate = (v?: string | null) =>
  v ? new Date(v).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
export const fmtDay = (v?: string | null) => (v ? new Date(v).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
export const pct = (v?: number | null) => (v === null || v === undefined ? '—' : `${Number(v).toFixed(v % 1 ? 1 : 0)}%`)
