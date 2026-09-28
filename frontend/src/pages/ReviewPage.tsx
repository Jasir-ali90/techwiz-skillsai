import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, History, RefreshCw } from 'lucide-react'
import type { Json } from '../api/client'
import { review } from '../api/endpoints'
import { DecisionModal } from '../components/DecisionModal'
import { RoleSelect } from '../components/pickers'
import { Badge, Button, Card, Empty, ErrorBox, PageHeader, Table, humanize } from '../components/ui'
import { useQuery } from '../lib/hooks'

const STATUSES = ['OPEN', 'APPROVED', 'REJECTED', 'EDITED', 'REGENERATED']

export function ReviewPage() {
  const [filters, setFilters] = useState({ status: 'OPEN', severity: '', job_role_id: '' })
  const [selected, setSelected] = useState<Json | null>(null)
  const q = useQuery(() => review.queue(filters), [JSON.stringify(filters)])
  const n = q.data?.length ?? 0
  return (
    <div className="stack">
      <PageHeader title="Review queue" subtitle="Items the automatic checks flagged for a person to decide on. Every decision is recorded, and the original result is kept." />
      <ErrorBox error={q.error} onRetry={q.reload} />
      <div className="segmented" role="tablist" aria-label="Review status">
        {STATUSES.map((s) => (
          <button key={s} role="tab" aria-selected={filters.status === s} className={filters.status === s ? 'on' : ''} onClick={() => setFilters({ ...filters, status: s })}>
            {s === 'OPEN' ? 'Waiting' : humanize(s)}
          </button>
        ))}
      </div>
      <Card
        title={filters.status === 'OPEN' ? `${n} waiting for a decision` : `${n} ${humanize(filters.status).toLowerCase()}`}
        actions={
          <>
            <select className="input" style={{ width: 180 }} value={filters.severity} onChange={(e) => setFilters({ ...filters, severity: e.target.value })} aria-label="Severity">
              <option value="">Errors and warnings</option>
              {['CRITICAL', 'ERROR', 'WARNING'].map((s) => <option key={s} value={s}>{humanize(s)} only</option>)}
            </select>
            <div style={{ width: 200 }}><RoleSelect value={filters.job_role_id} onChange={(v) => setFilters({ ...filters, job_role_id: v })} allowEmpty="All roles" /></div>
            <Button icon={RefreshCw} onClick={q.reload}>Refresh</Button>
          </>
        }
      >
        {q.data && !q.data.length ? (
          <Empty icon={CheckCircle2} title={filters.status === 'OPEN' ? "You're all caught up" : 'Nothing here'}>
            {filters.status === 'OPEN' ? 'No flagged items are waiting for review.' : 'No items with this status yet.'}
          </Empty>
        ) : (
          <Table
            rows={q.data}
            columns={[
              { key: 'severity', label: 'Severity', render: (f) => <Badge value={f.severity} /> },
              {
                key: 'message', label: 'What was found',
                render: (f) => (
                  <div style={{ maxWidth: 520 }}>
                    <div className="small">{f.message}</div>
                    <div className="small subtle" style={{ marginTop: 2 }}>{humanize(f.rule)}{f.requirement_code ? ` · ${f.requirement_code}` : ''}</div>
                  </div>
                ),
              },
              { key: 'plan_title', label: 'Plan', render: (f) => <Link to={`/plans/${f.plan_id}`} className="small">{f.plan_title}</Link> },
              { key: 'review_status', label: 'Status', render: (f) => <Badge value={f.review_status} /> },
              {
                key: 'a', label: '',
                render: (f) => (
                  <div className="row gap-xs" style={{ justifyContent: 'flex-end' }}>
                    {f.review_status === 'OPEN' && <Button size="sm" variant="primary" onClick={() => setSelected(f)}>Review</Button>}
                    <Link className="icon-btn" title="History" aria-label="History" to={`/audit?type=finding&id=${f.id}`}><History size={16} /></Link>
                  </div>
                ),
              },
            ]}
          />
        )}
      </Card>
      <DecisionModal finding={selected} onClose={() => setSelected(null)} onDone={q.reload} />
    </div>
  )
}
