import { useState } from 'react'
import { BookOpen, CheckCircle2, Clock, XCircle } from 'lucide-react'
import type { Json } from '../api/client'
import { plans, progress } from '../api/endpoints'
import { Badge, Button, Card, Empty, ErrorBox, Meter, PageHeader, Spinner, fmtDay, humanize } from '../components/ui'
import { useAction, useQuery } from '../lib/hooks'
import { SourceRef } from './PlanDetailPage'
import { ProgressView } from './ProgressPage'

/** The employee's own view: progress, their plan's modules, tick items off, take quizzes. */
export function MyOnboardingPage() {
  const dash = useQuery(() => progress.me())
  const planId = dash.data?.plan?.id
  const plan = useQuery(() => (planId ? plans.get(planId) : Promise.resolve(null)), [planId])
  if (dash.loading && !dash.data) return <Spinner />
  if (dash.error) return <ErrorBox error={dash.error} onRetry={dash.reload} />
  const d = dash.data
  const refresh = () => { dash.reload(); plan.reload() }
  return (
    <div className="stack">
      <PageHeader title={`Welcome, ${d.employee.name.split(' ')[0]}`} subtitle={`${d.employee.role} in ${d.employee.department}. You joined on ${fmtDay(d.employee.joining_date)}.`} />
      <ProgressView dash={d} self />
      {!planId && (
        <Card><Empty icon={BookOpen} title="Your plan is on its way">Your training manager hasn't created your onboarding plan yet. It will appear here as soon as it's ready.</Empty></Card>
      )}
      {plan.data && (
        <Card title="Your learning modules" icon={BookOpen} subtitle="Open a module, tick off each task as you finish it, and try the quiz.">
          <div>
            {plan.data.modules.map((m: Json) => <MyModule key={m.id} module={m} onChange={refresh} />)}
          </div>
        </Card>
      )}
    </div>
  )
}

function MyModule({ module: m, onChange }: { module: Json; onChange: () => void }) {
  const set = useAction((type: string, id: string, status: string) => progress.setItem(type, id, status))
  const toggle = async (type: string, item: Json) => {
    await set.run(type, item.id, item.completion_status === 'COMPLETED' ? 'NOT_STARTED' : 'COMPLETED')
    onChange()
  }
  const items = [...m.tasks.map((t: Json) => ({ ...t, _type: 'task', _text: t.description })), ...m.checklist.filter((c: Json) => c.is_required).map((c: Json) => ({ ...c, _type: 'checklist_item', _text: c.activity }))]
  const done = items.filter((i) => i.completion_status === 'COMPLETED').length
  return (
    <details className="module">
      <summary>
        <div className="grow">
          <div className="strong">{m.title}</div>
          <div className="row gap-sm small subtle wrap" style={{ marginTop: 4 }}>
            <span className="row gap-xs"><Clock size={13} /> {m.estimated_duration_minutes} min</span>
            <span>· {done} of {items.length} done</span>
            {m.quiz.length > 0 && <span>· {m.quiz.length} quiz question{m.quiz.length > 1 ? 's' : ''}</span>}
          </div>
        </div>
        <div style={{ width: 110 }}><Meter value={items.length ? (done / items.length) * 100 : 0} tone="accent" /></div>
        <Badge value={humanize(m.due_stage)} tone="info" plain />
      </summary>
      <div className="module-body stack">
        <p style={{ margin: 0 }}>{m.purpose}</p>
        {items.length > 0 && (
          <div>
            <div className="section-label">To do</div>
            {items.map((i) => {
              const isDone = i.completion_status === 'COMPLETED'
              return (
                <label key={i.id} className="item check" style={{ alignItems: 'flex-start', display: 'flex' }}>
                  <input type="checkbox" style={{ marginTop: 3 }} checked={isDone} onChange={() => toggle(i._type, i)} disabled={set.running} />
                  <span className="grow">
                    <span style={isDone ? { textDecoration: 'line-through', color: 'var(--text-3)' } : undefined}>{i._text}</span>
                    <span className="row wrap gap-sm" style={{ marginTop: 4 }}><Badge value={humanize(i.due_stage)} tone="info" plain /> <SourceRef item={i} /></span>
                  </span>
                </label>
              )
            })}
          </div>
        )}
        {m.quiz.length > 0 && (
          <div className="stack-sm">
            <div className="section-label">Check your understanding</div>
            {m.quiz.map((q: Json, i: number) => <QuizQuestion key={q.id} n={i + 1} q={q} onAnswered={onChange} />)}
          </div>
        )}
      </div>
    </details>
  )
}

function QuizQuestion({ q, n, onAnswered }: { q: Json; n: number; onAnswered: () => void }) {
  const multi = q.question_type === 'MULTIPLE_RESPONSE'
  const [picked, setPicked] = useState<string[]>([])
  const attempt = useAction(() => progress.attempt(q.id, picked))
  const r = attempt.result as Json
  return (
    <div className="card" style={{ boxShadow: 'none', background: 'var(--surface-2)' }}>
      <div className="card-body stack-sm">
        <div className="strong">{n}. {q.question}</div>
        {multi && <div className="small subtle">Choose all that apply.</div>}
        <div className="stack-sm">
          {q.options.map((o: string) => (
            <label key={o} className="check" style={{ display: 'flex' }}>
              <input
                type={multi ? 'checkbox' : 'radio'}
                name={q.id}
                checked={picked.includes(o)}
                onChange={() => setPicked(multi ? (picked.includes(o) ? picked.filter((x) => x !== o) : [...picked, o]) : [o])}
              />
              {o}
            </label>
          ))}
        </div>
        <div className="row gap-sm wrap">
          <Button size="sm" variant="primary" disabled={!picked.length} loading={attempt.running} onClick={async () => { await attempt.run(); onAnswered() }}>
            {r ? 'Try again' : 'Check answer'}
          </Button>
          {r && (
            <span className={`row gap-xs strong small ${r.is_correct ? 'good' : 'bad'}`}>
              {r.is_correct ? <CheckCircle2 size={16} /> : <XCircle size={16} />} {r.is_correct ? 'Correct' : 'Not quite'}
            </span>
          )}
        </div>
        {r?.explanation && <div className="small muted">{r.explanation}</div>}
      </div>
    </div>
  )
}
