import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { History, Search } from 'lucide-react'
import type { Json } from '../api/client'
import { review } from '../api/endpoints'
import { Badge, Button, Card, Empty, Field, JsonView, PageHeader, Spinner, Table, fmtDate, humanize } from '../components/ui'
import { useQuery } from '../lib/hooks'

const TYPES = ['plan', 'finding', 'requirement', 'document', 'task', 'checklist_item', 'module', 'assessment', 'config']

export function AuditTable({ entityType, entityId }: { entityType: string; entityId: string }) {
  const q = useQuery(() => review.audit(entityType, entityId), [entityType, entityId])
  if (q.loading) return <Spinner />
  return (
    <div className="stack">
      <Card title="Change history" subtitle="Entries can't be edited or deleted, not even by an administrator.">
        <Table
          rows={q.data?.history}
          empty="No changes recorded yet."
          columns={[
            { key: 'created_at', label: 'When', render: (h) => <span className="small nowrap">{fmtDate(h.created_at)}</span> },
            { key: 'action', label: 'Action', render: (h) => <Badge value={h.action} tone="neutral" plain /> },
            { key: 'reason', label: 'Reason', render: (h) => <span className="small">{h.reason ?? '—'}</span> },
            { key: 'change', label: 'What changed', render: (h) => <ChangeCell before={h.before} after={h.after} /> },
          ]}
        />
      </Card>
      {q.data?.review_decisions?.length > 0 && (
        <Card title="Review decisions" subtitle="The original check result is kept next to each decision.">
          <Table
            rows={q.data.review_decisions}
            columns={[
              { key: 'created_at', label: 'When', render: (d) => <span className="small nowrap">{fmtDate(d.created_at)}</span> },
              { key: 'decision', label: 'Decision', render: (d) => <Badge value={d.decision} tone="info" /> },
              { key: 'reason', label: 'Reason' },
              { key: 'original', label: 'Original finding', render: (d) => <span className="small">{d.original_finding?.message}</span> },
              { key: 'edits', label: 'Details', render: (d) => <JsonView value={{ edited_fields: d.edited_fields, outcome: d.outcome }} collapsed label="details" /> },
            ]}
          />
        </Card>
      )}
    </div>
  )
}

function ChangeCell({ before, after }: { before: Json; after: Json }) {
  if (!before && !after) return <span className="muted">—</span>
  return <JsonView value={{ before, after }} collapsed label="change" />
}

export function AuditPage() {
  const [params, setParams] = useSearchParams()
  const [type, setType] = useState(params.get('type') ?? 'plan')
  const [id, setId] = useState(params.get('id') ?? '')
  const active = params.get('id')
  return (
    <div className="stack">
      <PageHeader title="Activity log" subtitle="Every change and decision, in order. Open a plan, finding or requirement to see its full history." />
      <Card>
        <form className="form-grid" onSubmit={(e) => { e.preventDefault(); setParams({ type, id: id.trim() }) }}>
          <Field label="What to look up">
            <select className="input" value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select>
          </Field>
          <Field label="ID or code" hint="A requirement code such as R012, a settings name, or an ID copied from a page">
            <input className="input" value={id} onChange={(e) => setId(e.target.value)} placeholder="e.g. R012" />
          </Field>
          <div className="row" style={{ alignItems: 'flex-end' }}><Button variant="primary" icon={Search} type="submit" disabled={!id.trim()}>Show history</Button></div>
        </form>
      </Card>
      {active ? <AuditTable entityType={params.get('type') ?? 'plan'} entityId={active} /> : <Card><Empty icon={History} title="Look something up">Choose what to look up and enter its ID or code. History links on other pages open here directly.</Empty></Card>}
    </div>
  )
}
