import type { Json } from '../api/client'
import { progress } from '../api/endpoints'
import { Badge, Card, Meter, PageHeader, Spinner, Stat, humanize, pct } from '../components/ui'
import { useQuery } from '../lib/hooks'

export function DashboardsPage() {
  const q = useQuery(() => progress.roles())
  if (!q.data) return <Spinner />
  return (
    <div className="stack">
      <PageHeader title="Role insights" subtitle="What each role has to learn, and how its new hires are getting on." />
      <div className="grid grid-2">
        {q.data.map((r: Json) => (
          <Card key={r.role_code} title={r.role_title} subtitle={r.department}>
            <div className="stack">
              <div className="grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
                <Stat label="Requirements" value={r.requirements.total} hint={`${r.requirements.mandatory} mandatory`} />
                <Stat label="New hires" value={r.employees} />
                <Stat label="Avg coverage" value={pct(r.plans.average_coverage)} tone={r.plans.average_coverage >= 100 ? 'good' : 'warn'} />
              </div>
              <div className="row gap-sm"><span className="small muted nowrap">Average progress</span><Meter value={r.completion.average_progress} tone="accent" /><span className="small strong">{pct(r.completion.average_progress)}</span></div>
              <div className="row wrap gap-sm">
                {Object.entries(r.plans.by_verification_status).map(([k, v]) => <Badge key={k} value={`${humanize(k)} · ${v}`} tone={k === 'VERIFIED' ? 'good' : 'warn'} />)}
                {Object.entries(r.completion.by_status).map(([k, v]) => <Badge key={k} value={`${humanize(k)} · ${v}`} tone={k === 'ON_TRACK' || k === 'COMPLETED' ? 'good' : k === 'BEHIND_SCHEDULE' ? 'bad' : 'warn'} />)}
              </div>
              <div className="small muted">Why they apply: {Object.entries(r.requirements.by_mapping_method).map(([k, v]) => `${v} ${humanize(k).toLowerCase()}`).join(' · ')}</div>
              <div className="row wrap gap-xs">{r.requirements.competencies.slice(0, 12).map((c: string) => <span key={c} className="chip">{c}</span>)}</div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
