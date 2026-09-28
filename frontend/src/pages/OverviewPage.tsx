import { AlertTriangle, CheckCircle2, ClipboardCheck, Cpu, GraduationCap, Inbox, ListChecks, TrendingUp, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Json } from '../api/client'
import { genai, matrix, progress } from '../api/endpoints'
import { Avatar, Badge, Card, CardLink, Empty, ErrorBox, Meter, MeterLabel, PageHeader, Spinner, Stat, Table, humanize, pct } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useQuery } from '../lib/hooks'

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export function OverviewPage() {
  const { user, can } = useAuth()
  const dash = useQuery(() => progress.admin())
  const summary = useQuery(() => matrix.summary())
  const ai = useQuery(() => genai.status())

  if (dash.loading && !dash.data) return <Spinner />
  const d = dash.data
  const s = summary.data
  const behind = d?.employees.by_status?.BEHIND_SCHEDULE ?? 0
  const verified = d?.training_plans.by_verification_status?.VERIFIED ?? 0
  return (
    <div className="stack">
      <PageHeader
        title={`${greeting()}, ${user?.full_name?.split(' ')[0] ?? 'there'}`}
        subtitle="Here's how onboarding is going across Nexora Labs today."
        actions={can(...GENERATORS) && <Link className="btn btn-primary btn-md" to="/plans?tab=generate"><ClipboardCheck size={16} /> Create a plan</Link>}
      />
      <ErrorBox error={dash.error} onRetry={dash.reload} />
      {d && (
        <>
          <div className="grid grid-stats">
            <Stat icon={Users} label="New hires" value={d.employees.total} hint={behind ? `${behind} behind schedule` : 'All on track'} tone={behind ? 'bad' : 'good'} />
            <Stat icon={ClipboardCheck} label="Active plans" value={d.training_plans.current} hint={`${verified} fully verified`} tone={verified === d.training_plans.current ? 'good' : 'warn'} />
            <Stat icon={TrendingUp} label="Average progress" value={pct(d.completion.average_overall_progress)} hint="Across all current plans" tone="info" />
            <Stat icon={GraduationCap} label="Assessment pass rate" value={pct(d.assessment_scores.pass_rate)} hint={d.assessment_scores.results ? `${d.assessment_scores.results} results so far` : 'No results yet'} />
            <Stat icon={Inbox} label="Waiting for review" value={d.manual_reviews.open} hint={d.manual_reviews.open ? 'Needs a decision' : 'Nothing waiting'} tone={d.manual_reviews.open ? 'warn' : 'good'} />
            <Stat icon={AlertTriangle} label="Flagged document text" value={d.flagged_content.suspicious_chunks} hint="Kept out of every AI prompt" tone={d.flagged_content.suspicious_chunks ? 'warn' : 'good'} />
          </div>

          <div className="grid grid-2">
            <Card title="Who needs a hand" subtitle="Behind the pace expected for their start date" icon={Users} actions={<CardLink to="/progress">All progress</CardLink>}>
              {d.employees_behind_schedule.length ? (
                <div className="stack-sm">
                  {d.employees_behind_schedule.slice(0, 6).map((r: Json) => (
                    <Link key={r.employee_code} className="row gap person-link" to={r.employee_id ? `/progress?employee=${r.employee_id}` : '/progress'}>
                      <Avatar name={r.name} />
                      <div className="grow">
                        <div className="row between gap-sm">
                          <span className="strong">{r.name}</span>
                          <span className="small subtle nowrap">Day {r.days}</span>
                        </div>
                        <div className="row gap-sm" style={{ marginTop: 4 }}>
                          <Meter value={r.progress} tone="bad" />
                          <span className="small muted nowrap">{pct(r.progress)} of {pct(r.expected)} expected</span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty icon={CheckCircle2} title="Everyone is on track">No new hire is behind schedule.</Empty>
              )}
            </Card>

            <Card title="Waiting for review" subtitle="Items the automatic checks couldn't settle" icon={Inbox} actions={<CardLink to="/review">Open queue</CardLink>}>
              {Object.keys(d.manual_reviews.by_rule).length ? (
                <Table
                  rows={Object.entries(d.manual_reviews.by_rule).map(([rule, n]) => ({ rule, n }))}
                  rowKey={(r) => r.rule}
                  columns={[
                    { key: 'rule', label: 'Check', render: (r) => humanize(r.rule) },
                    { key: 'n', label: 'Open', width: '80px' },
                  ]}
                />
              ) : (
                <Empty icon={CheckCircle2} title="All clear">Nothing is waiting for a decision.</Empty>
              )}
            </Card>
          </div>

          <Card title="Mandatory training coverage by role" subtitle="How much of each role's required training the current plans include" icon={ListChecks} actions={<CardLink to="/dashboards">Role insights</CardLink>}>
            <Table
              rows={d.compliance_coverage}
              rowKey={(r) => r.role_code}
              columns={[
                { key: 'role_title', label: 'Role', render: (r) => <span className="strong">{r.role_title}</span> },
                { key: 'department', label: 'Department', render: (r) => <span className="muted">{r.department}</span> },
                { key: 'mandatory_requirements', label: 'Mandatory items' },
                { key: 'verified_plans', label: 'Verified plans', render: (r) => `${r.verified_plans} of ${r.plans}` },
                { key: 'cov', label: 'Coverage', width: '220px', render: (r) => <MeterLabel value={r.average_mandatory_coverage} /> },
              ]}
            />
          </Card>

          <div className="grid grid-2">
            <Card title="AI writing service" subtitle="Tried in order until one succeeds" icon={Cpu} actions={<CardLink to="/ai">AI settings</CardLink>}>
              {ai.data ? (
                <div className="stack-sm">
                  {ai.data.chain.map((p: Json, i: number) => (
                    <div key={p.provider} className="row gap-sm">
                      <span className="step-no">{i + 1}</span>
                      <span className="grow strong">{humanize(p.provider)}</span>
                      <Badge value={p.usable ? 'Ready' : 'Not set up'} tone={p.usable ? 'good' : 'muted'} />
                    </div>
                  ))}
                  <p className="small muted" style={{ margin: '8px 0 0' }}>
                    Each service gets up to {ai.data.retry?.max_attempts ?? 3} tries before the next one takes over.
                  </p>
                </div>
              ) : (
                <Spinner />
              )}
            </Card>
            <Card title="Requirement matrix" subtitle="The checklist every plan is measured against" icon={ListChecks} actions={<CardLink to="/matrix">Open</CardLink>}>
              {s ? (
                <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
                  {Object.entries(s.srs_minimums).map(([k, v]: [string, Json]) => (
                    <Stat key={k} label={humanize(k)} value={v.actual} hint={v.met ? `Target ${v.required} met` : `Below target of ${v.required}`} tone={v.met ? 'good' : 'bad'} />
                  ))}
                </div>
              ) : (
                <Spinner />
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
