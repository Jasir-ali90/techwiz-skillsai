import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, CalendarDays, CheckCircle2, Circle, Flag, GraduationCap, Lightbulb, ListTodo, ShieldCheck, Target, TriangleAlert } from 'lucide-react'
import type { Json } from '../api/client'
import { progress } from '../api/endpoints'
import { EmployeeSelect } from '../components/pickers'
import { Badge, Card, Empty, ErrorBox, MeterLabel, PageHeader, ProgressRing, Spinner, Stat, Table, fmtDay, humanize, pct } from '../components/ui'
import { useQuery } from '../lib/hooks'

export function ProgressPage() {
  const [params, setParams] = useSearchParams()
  const employeeId = params.get('employee') ?? ''
  return (
    <div className="stack">
      <PageHeader
        title="Employee progress"
        subtitle="Worked out live from each person's start date and the onboarding schedule."
        actions={<div style={{ width: 340, maxWidth: '100%' }}><EmployeeSelect value={employeeId} onChange={(v) => setParams(v ? { employee: v } : {})} /></div>}
      />
      {employeeId ? <EmployeeProgress employeeId={employeeId} /> : <Card><Empty icon={Target} title="Choose a new hire">Pick someone from the list above to see how their onboarding is going.</Empty></Card>}
    </div>
  )
}

export function EmployeeProgress({ employeeId }: { employeeId: string }) {
  const d = useQuery(() => progress.employeeDashboard(employeeId), [employeeId])
  if (d.loading && !d.data) return <Spinner />
  if (d.error) return <ErrorBox error={d.error} onRetry={d.reload} />
  return <ProgressView dash={d.data} />
}

const STATUS_TONE: Record<string, string> = { ON_TRACK: 'good', COMPLETED: 'good', BEHIND_SCHEDULE: 'bad', REQUIRES_ATTENTION: 'warn', ASSESSMENT_REQUIRED: 'warn' }

export function ProgressView({ dash, self }: { dash: Json; self?: boolean }) {
  const p = dash.onboarding_progress
  const tone = STATUS_TONE[p.status] ?? 'accent'
  const gap = (p.expected_progress ?? 0) - (p.overall_progress ?? 0)
  const headline =
    p.status === 'COMPLETED' ? 'Onboarding complete'
      : gap > 5 ? (self ? `You're a little behind: ${pct(p.expected_progress)} was expected by today` : `Behind pace: ${pct(p.expected_progress)} was expected by today`)
        : self ? "You're on track" : 'Keeping pace with the schedule'
  return (
    <div className="stack">
      <Card>
        <div className="row wrap" style={{ gap: 24 }}>
          <ProgressRing value={p.overall_progress} tone={tone} />
          <div className="grow" style={{ minWidth: 240 }}>
            <div className="row gap-sm wrap"><Badge value={p.status} /> <span className="small muted">Day {p.days_since_joining} since joining</span></div>
            <h2 style={{ marginTop: 10 }}>{headline}</h2>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              {dash.completed_modules.length} of {dash.assigned_modules.length} modules finished
              {dash.plan?.id && !self && <> · <Link to={`/plans/${dash.plan.id}`}>Open plan <ArrowRight size={13} style={{ verticalAlign: '-2px' }} /></Link></>}
            </p>
          </div>
        </div>
      </Card>
      <div className="grid grid-stats">
        <Stat icon={ListTodo} label="Modules done" value={`${dash.completed_modules.length} / ${dash.assigned_modules.length}`} />
        <Stat icon={CheckCircle2} label="Quiz score" value={pct(p.quiz_score)} hint={p.quiz_score === null ? 'No answers yet' : undefined} />
        <Stat icon={GraduationCap} label="Assessment score" value={pct(p.assessment_score)} hint={p.assessment_score === null ? 'Not assessed yet' : undefined} />
        <Stat icon={ShieldCheck} label="Plan check" value={<Badge value={dash.plan?.verification_status ?? 'NO_PLAN'} />} />
      </div>
      <Card title="Milestones" icon={Flag} subtitle="Each onboarding stage and how much of it is done">
        <Table
          rows={dash.milestones}
          rowKey={(m) => m.stage}
          columns={[
            {
              key: 'name', label: 'Stage',
              render: (m) => (
                <span className="row gap-sm">
                  {m.percent >= 100 ? <CheckCircle2 size={16} className="good" aria-label="Done" /> : m.reached ? <TriangleAlert size={16} className="bad" aria-label="Overdue" /> : <Circle size={16} className="subtle" aria-label="Upcoming" />}
                  <strong>{m.name}</strong>
                  {m.reached && m.percent < 100 && <Badge value="Overdue" tone="bad" />}
                </span>
              ),
            },
            { key: 'due_date', label: 'Due', render: (m) => <span className="small muted nowrap">{fmtDay(m.due_date)}</span> },
            { key: 'items', label: 'Done', render: (m) => <span className="small">{m.completed} of {m.items}</span> },
            { key: 'bar', label: 'Progress', width: '240px', render: (m) => <MeterLabel value={m.percent} /> },
          ]}
        />
      </Card>
      <div className="grid grid-2">
        <Card title={self ? 'Where to focus' : 'Weak areas'} icon={TriangleAlert} subtitle="From quiz answers, assessments and overdue tasks">
          {dash.weak_areas.length ? (
            <div className="stack-sm">
              {dash.weak_areas.map((w: Json) => (
                <div key={w.competency} className="row between gap-sm wrap">
                  <span className="strong">{w.competency}</span>
                  <span className="row gap-xs wrap">{w.signals.map((s: Json) => <Badge key={s.signal} value={s.signal} tone="warn" />)}</span>
                </div>
              ))}
            </div>
          ) : (
            <Empty icon={CheckCircle2} title="Nothing to worry about">No weak areas found.</Empty>
          )}
        </Card>
        <Card title="Suggested next steps" icon={Lightbulb} subtitle="Based on simple rules, not AI">
          {dash.recommendations.length ? (
            <div>
              {dash.recommendations.map((r: Json, i: number) => (
                <div key={i} className="item">
                  <div className="small">{r.message}</div>
                  <div style={{ marginTop: 4 }}><Badge value={r.type} tone="info" plain /></div>
                </div>
              ))}
            </div>
          ) : (
            <Empty icon={CheckCircle2} title="No suggestions">Everything looks good.</Empty>
          )}
        </Card>
      </div>
      <Card title="Coming up" icon={CalendarDays}>
        <Table
          rows={dash.upcoming_activities}
          rowKey={(u) => u.id}
          empty="All caught up. Nothing is due."
          columns={[
            { key: 'title', label: 'Activity', render: (u) => <span className="small">{u.title}</span> },
            { key: 'type', label: 'Type', render: (u) => <Badge value={humanize(u.type)} tone="neutral" plain /> },
            { key: 'stage', label: 'Stage', render: (u) => humanize(u.stage) },
            { key: 'due_date', label: 'Due', render: (u) => <span className="small nowrap">{fmtDay(u.due_date)}</span> },
          ]}
        />
      </Card>
    </div>
  )
}
