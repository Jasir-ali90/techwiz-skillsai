import { useState } from 'react'
import { Activity, AlertOctagon, AlertTriangle, CheckCircle2, Flame, ShieldAlert, Sparkles, Users } from 'lucide-react'
import type { Json } from '../api/client'
import { progress } from '../api/endpoints'
import { Badge, Card, Empty, Meter, PageHeader, Spinner, Stat, Table, Tabs, humanize, pct } from '../components/ui'
import { useQuery } from '../lib/hooks'

export function DashboardsPage() {
  const [tab, setTab] = useState<'roles' | 'predictive'>('roles')

  return (
    <div className="stack">
      <PageHeader
        title="Intelligence & Dashboards"
        subtitle="Role curriculum matrices, new-hire completion tracking, attrition risk radar, and diagnostic confusion heatmaps."
      />
      <Tabs
        active={tab}
        onChange={(t) => setTab(t as 'roles' | 'predictive')}
        tabs={[
          { id: 'roles', label: 'Role Insights', icon: Users },
          { id: 'predictive', label: 'Predictive Analytics & Risk Radar', icon: Flame },
        ]}
      />

      {tab === 'roles' && <RolesDashboard />}
      {tab === 'predictive' && <PredictiveDashboard />}
    </div>
  )
}

function RolesDashboard() {
  const q = useQuery(() => progress.roles())
  if (!q.data) return <Spinner label="Loading role insights..." />

  return (
    <div className="grid grid-2">
      {q.data.map((r: Json) => (
        <Card key={r.role_code} title={r.role_title} subtitle={r.department}>
          <div className="stack">
            <div className="grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
              <Stat label="Requirements" value={r.requirements.total} hint={`${r.requirements.mandatory} mandatory`} />
              <Stat label="New hires" value={r.employees} />
              <Stat label="Avg coverage" value={pct(r.plans.average_coverage)} tone={r.plans.average_coverage >= 100 ? 'good' : 'warn'} />
            </div>
            <div className="row gap-sm">
              <span className="small muted nowrap">Average progress</span>
              <Meter value={r.completion.average_progress} tone="accent" />
              <span className="small strong">{pct(r.completion.average_progress)}</span>
            </div>
            <div className="row wrap gap-sm">
              {Object.entries(r.plans.by_verification_status).map(([k, v]) => (
                <Badge key={k} value={`${humanize(k)} · ${v}`} tone={k === 'VERIFIED' ? 'good' : 'warn'} />
              ))}
              {Object.entries(r.completion.by_status).map(([k, v]) => (
                <Badge
                  key={k}
                  value={`${humanize(k)} · ${v}`}
                  tone={k === 'ON_TRACK' || k === 'COMPLETED' ? 'good' : k === 'BEHIND_SCHEDULE' ? 'bad' : 'warn'}
                />
              ))}
            </div>
            <div className="small muted">
              Why they apply: {Object.entries(r.requirements.by_mapping_method).map(([k, v]) => `${v} ${humanize(k).toLowerCase()}`).join(' · ')}
            </div>
            <div className="row wrap gap-xs">
              {r.requirements.competencies.slice(0, 12).map((c: string) => (
                <span key={c} className="chip">{c}</span>
              ))}
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

function PredictiveDashboard() {
  const q = useQuery(() => progress.predictiveAnalytics())
  if (!q.data) return <Spinner label="Synthesizing predictive risk factors and quiz failure heatmaps..." />

  const data = q.data as Json

  return (
    <div className="stack gap-lg">
      {/* Risk Metrics Overview */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
        <Card>
          <div className="row between items-center">
            <Stat label="Critical Attrition Risk" value={data.high_risk_count} tone="bad" hint="Immediate 1-on-1 needed" />
            <AlertOctagon size={28} style={{ color: 'var(--red, #ef4444)' }} />
          </div>
        </Card>
        <Card>
          <div className="row between items-center">
            <Stat label="Moderate Risk / Watch" value={data.medium_risk_count} tone="warn" hint="Tracking behind pace" />
            <AlertTriangle size={28} style={{ color: 'var(--amber, #f59e0b)' }} />
          </div>
        </Card>
        <Card>
          <div className="row between items-center">
            <Stat label="On-Track & Thriving" value={data.low_risk_count} tone="good" hint="Healthy progression" />
            <CheckCircle2 size={28} style={{ color: 'var(--green, #10b981)' }} />
          </div>
        </Card>
        <Card>
          <div className="row between items-center">
            <Stat label="Total Cohort Analyzed" value={data.risk_roster?.length ?? 0} hint="Real-time telemetry" />
            <Activity size={28} style={{ color: 'var(--primary, #3b82f6)' }} />
          </div>
        </Card>
      </div>

      {/* AI Prescriptive Interventions */}
      {data.prescriptions && data.prescriptions.length > 0 && (
        <Card
          title={
            <div className="row gap-sm items-center">
              <Sparkles size={18} style={{ color: 'var(--accent, #a855f7)' }} />
              <span>Prescriptive AI Diagnostic Interventions</span>
            </div>
          }
          subtitle="Targeted actions calculated based on quiz failure spikes and onboarding stage delays"
        >
          <div className="grid grid-2" style={{ gap: 12 }}>
            {data.prescriptions.map((p: Json, i: number) => (
              <div
                key={i}
                style={{
                  padding: 14,
                  borderRadius: 10,
                  border: '1px solid var(--border)',
                  background: 'rgba(255, 255, 255, 0.02)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div className="row between items-center">
                  <span className="strong" style={{ fontSize: 14 }}>{p.action}</span>
                  <Badge
                    value={p.priority}
                    tone={p.priority === 'HIGH' ? 'bad' : p.priority === 'MEDIUM' ? 'warn' : 'info'}
                  />
                </div>
                <div className="small muted">Target: <strong style={{ color: 'var(--fg)' }}>{p.target}</strong></div>
                <p className="small" style={{ lineHeight: 1.5, margin: 0 }}>{p.recommendation}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Competency Confusion Heatmap */}
      <Card
        title={
          <div className="row gap-sm items-center">
            <ShieldAlert size={18} style={{ color: 'var(--amber, #f59e0b)' }} />
            <span>Policy & Competency Confusion Heatmap</span>
          </div>
        }
        subtitle="Identifies knowledge base clauses with highest quiz failure rates across all new hires"
      >
        {!data.confusion_heatmap || data.confusion_heatmap.length === 0 ? (
          <Empty title="No failure telemetry">No quiz attempts recorded yet.</Empty>
        ) : (
          <Table
            rows={data.confusion_heatmap}
            rowKey={(r: Json) => r.competency}
            columns={[
              {
                key: 'competency',
                label: 'Competency / Policy Domain',
                render: (r: Json) => (
                  <div>
                    <span className="strong">{r.competency}</span>
                    <div className="small muted">{r.total_attempts} total attempts ({r.failed_attempts} failed)</div>
                  </div>
                ),
              },
              {
                key: 'confusion_rate_percent',
                label: 'Confusion Rate',
                render: (r: Json) => (
                  <div style={{ minWidth: 160 }}>
                    <div className="row between gap-sm small">
                      <span className="strong">{r.confusion_rate_percent}%</span>
                      <span className="muted">{r.failed_attempts} of {r.total_attempts}</span>
                    </div>
                    <Meter
                      value={r.confusion_rate_percent}
                      tone={r.severity === 'HIGH' ? 'bad' : r.severity === 'MEDIUM' ? 'warn' : 'accent'}
                    />
                  </div>
                ),
              },
              {
                key: 'severity',
                label: 'Severity Level',
                render: (r: Json) => (
                  <Badge
                    value={r.severity}
                    tone={r.severity === 'HIGH' ? 'bad' : r.severity === 'MEDIUM' ? 'warn' : 'good'}
                  />
                ),
              },
            ]}
          />
        )}
      </Card>

      {/* Attrition Risk Roster */}
      <Card
        title={
          <div className="row gap-sm items-center">
            <Flame size={18} style={{ color: 'var(--red, #ef4444)' }} />
            <span>Employee Attrition & Struggle Risk Roster</span>
          </div>
        }
        subtitle="Ranked priority list of team members encountering friction during their onboarding journey"
      >
        {!data.risk_roster || data.risk_roster.length === 0 ? (
          <Empty title="No employees monitored">No active onboarding plans found.</Empty>
        ) : (
          <Table
            rows={data.risk_roster}
            rowKey={(r: Json) => r.employee_id}
            columns={[
              {
                key: 'name',
                label: 'Employee',
                render: (r: Json) => (
                  <div>
                    <span className="strong">{r.name}</span>
                    <div className="small muted font-mono">{r.employee_code} · {r.department}</div>
                  </div>
                ),
              },
              {
                key: 'role_title',
                label: 'Role & Tenure',
                render: (r: Json) => (
                  <div>
                    <span>{r.role_title}</span>
                    <div className="small muted">{r.days_in} days enrolled</div>
                  </div>
                ),
              },
              {
                key: 'progress_percent',
                label: 'Progress',
                render: (r: Json) => (
                  <div style={{ minWidth: 120 }}>
                    <span className="small strong">{pct(r.progress_percent)}</span>
                    <Meter value={r.progress_percent} tone="accent" />
                  </div>
                ),
              },
              {
                key: 'risk_tier',
                label: 'Risk Tier',
                render: (r: Json) => (
                  <Badge
                    value={`${r.risk_tier} (${r.risk_score})`}
                    tone={r.risk_tier === 'HIGH' ? 'bad' : r.risk_tier === 'MEDIUM' ? 'warn' : 'good'}
                  />
                ),
              },
              {
                key: 'primary_risk_factor',
                label: 'Telemetry Warning Flags',
                render: (r: Json) => (
                  <span className="small" style={{ color: r.risk_tier === 'HIGH' ? 'var(--red)' : 'var(--muted)' }}>
                    {r.primary_risk_factor}
                  </span>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}

