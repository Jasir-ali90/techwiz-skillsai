import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, FileSearch, ListChecks, UserCheck } from 'lucide-react'
import { ApiError } from '../api/client'
import { Logo } from '../components/Logo'
import { Alert, Avatar, Button, Field } from '../components/ui'
import { useAuth } from '../lib/auth'

const DEMO = [
  { email: 'admin@nexoralabs.io', password: 'Admin@123', label: 'Admin', desc: 'Everything, including settings' },
  { email: 'training@nexoralabs.io', password: 'Train@123', label: 'Training manager', desc: 'Creates and updates plans' },
  { email: 'reviewer@nexoralabs.io', password: 'Review@123', label: 'Reviewer', desc: 'Approves flagged items' },
  { email: 'manager@nexoralabs.io', password: 'Manage@123', label: 'Manager', desc: "Follows the team's progress" },
  { email: 'employee@nexoralabs.io', password: 'Employ@123', label: 'Employee', desc: 'Sees their own onboarding' },
  { email: 'evaluator@nexoralabs.io', password: 'Evaluate@123', label: 'Evaluator', desc: 'Read-only look around' },
]

const POINTS = [
  { icon: FileSearch, title: 'Built from your own policies', text: 'Every task and quiz links back to the document and section it came from.' },
  { icon: ListChecks, title: 'Checked before anyone sees it', text: 'Rule-based checks confirm nothing mandatory is missing or out of date.' },
  { icon: UserCheck, title: 'People stay in charge', text: 'Anything uncertain goes to a reviewer, and every decision is recorded.' },
]

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function signIn(e: string, p: string) {
    setBusy(e)
    setError(null)
    try {
      await login(e, p)
      navigate(e.startsWith('employee') ? '/me' : '/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server. Is the API running?')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="login">
      <aside className="login-aside">
        <div className="login-brand">
          <Logo height={46} surface="dark" />
          <span className="tagline">Learn<i aria-hidden />Practice<i aria-hidden />Achieve</span>
        </div>
        <div>
          <h2>Onboarding plans your team can trust.</h2>
          <p>Personal training plans for every new hire at Nexora Labs, written from company documents and checked line by line.</p>
        </div>
        <div className="login-points">
          {POINTS.map((p) => (
            <div className="login-point" key={p.title}>
              <span className="login-point-icon"><p.icon size={18} /></span>
              <div>
                <strong>{p.title}</strong>
                <span>{p.text}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="login-main">
        <div className="login-form stack">
          <div>
            <h1>Sign in</h1>
            <p className="muted" style={{ marginTop: 6 }}>Welcome back. Use your work email.</p>
          </div>
          <form className="stack-sm" onSubmit={(e: FormEvent) => { e.preventDefault(); signIn(email, password) }}>
            <Field label="Email">
              <input className="input" type="email" autoComplete="username" placeholder="name@nexoralabs.io" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <Field label="Password">
              <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </Field>
            {error && <Alert kind="error">{error}</Alert>}
            <div style={{ paddingTop: 6 }}>
              <Button variant="primary" size="lg" type="submit" block loading={busy === email && !!email}>
                Sign in
              </Button>
            </div>
          </form>
          <div className="or">or try a demo account</div>
          <div className="demo-list">
            {DEMO.map((d) => (
              <button key={d.email} className="demo" disabled={!!busy} onClick={() => signIn(d.email, d.password)}>
                <Avatar name={d.label} />
                <div className="grow">
                  <div className="demo-name">{d.label}</div>
                  <div className="demo-desc">{d.desc}</div>
                </div>
                {busy === d.email ? <span className="spinner spinner-sm" /> : <ChevronRight size={16} />}
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
