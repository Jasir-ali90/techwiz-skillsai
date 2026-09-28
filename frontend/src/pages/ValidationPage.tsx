import { useState } from 'react'
import { AlertTriangle, Scale, SlidersHorizontal } from 'lucide-react'
import type { Json } from '../api/client'
import { validation } from '../api/endpoints'
import { Badge, Button, Card, CardLink, JsonEditor, PageHeader, Spinner, Table, Tabs, humanize } from '../components/ui'
import { useAction, useQuery } from '../lib/hooks'
import { useAuth } from '../lib/auth'

export function ValidationPage() {
  const [tab, setTab] = useState('rules')
  return (
    <div>
      <PageHeader title="Quality checks" subtitle="The fixed rules every plan is checked against. No AI is involved. Changes apply from the next check, with no code changes needed." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'rules', label: 'Check rules', icon: SlidersHorizontal }, { id: 'business', label: 'Company rules', icon: Scale }, { id: 'contradictions', label: 'Conflicting documents', icon: AlertTriangle }]} />
      {tab === 'rules' && <Rules />}
      {tab === 'business' && <Business />}
      {tab === 'contradictions' && <Contradictions />}
    </div>
  )
}

function Rules() {
  const { can } = useAuth()
  const q = useQuery(() => validation.rules())
  const [editing, setEditing] = useState<Json | null>(null)
  const [draft, setDraft] = useState<Json>(null)
  const save = useAction((changes: Json) => validation.updateRules(changes), 'Saved. The next check uses these settings.')
  if (!q.data) return <Spinner />
  const toggle = async (r: Json) => { await save.run({ [r.name]: { enabled: !r.enabled } }); q.reload() }
  return (
    <Card title={`${q.data.rules.filter((r: Json) => r.enabled).length} of ${q.data.rules.length} checks switched on`} subtitle={`Settings version ${q.data.version}`}>
      <Table
        rows={q.data.rules}
        rowKey={(r) => r.name}
        columns={[
          { key: 'name', label: 'Check', render: (r) => <><div className="strong">{humanize(r.name)}</div><div className="small muted" style={{ maxWidth: 460 }}>{r.description}</div></> },
          { key: 'settings', label: 'Settings', render: (r) => <span className="source">{Object.entries(r.settings).filter(([k]) => k !== 'enabled' && typeof r.settings[k] !== 'object').map(([k, v]) => `${k}=${v}`).join(' ') || '—'}</span> },
          { key: 'enabled', label: 'Status', render: (r) => <Badge value={r.enabled ? 'On' : 'Off'} tone={r.enabled ? 'good' : 'muted'} /> },
          { key: 'a', label: '', render: (r) => can('ADMIN') && <div className="row gap-sm"><Button size="sm" loading={save.running} onClick={() => toggle(r)}>{r.enabled ? 'Turn off' : 'Turn on'}</Button><Button size="sm" variant="ghost" onClick={() => { setEditing(r); setDraft(r.settings) }}>Adjust</Button></div> },
        ]}
      />
      {editing && (
        <div className="stack" style={{ marginTop: 16 }}>
          <h3>Adjust {humanize(editing.name).toLowerCase()}</h3>
          <JsonEditor initial={editing.settings} resetKey={editing.name} rows={8} onChange={(v, ok) => ok && setDraft(v)} />
          <div className="row gap-sm"><Button variant="primary" loading={save.running} onClick={async () => { await save.run({ [editing.name]: draft }); setEditing(null); q.reload() }}>Save</Button><Button onClick={() => setEditing(null)}>Cancel</Button></div>
        </div>
      )}
    </Card>
  )
}

function Business() {
  const q = useQuery(() => validation.rules())
  return (
    <Card title="Company rules" subtitle="Extra rules specific to Nexora Labs, such as deadlines for certain roles" actions={<CardLink to="/config">Edit in configuration</CardLink>}>
      <Table
        rows={q.data?.business_rules}
        rowKey={(r) => r.name}
        columns={[
          { key: 'name', label: 'Rule', render: (r) => <><div className="strong">{humanize(r.name)}</div><div className="small muted">{r.message}</div></> },
          { key: 'type', label: 'Type', render: (r) => <Badge value={r.type} tone="neutral" plain /> },
          { key: 'severity', label: 'Severity', render: (r) => <Badge value={r.severity} /> },
          { key: 'roles', label: 'Roles', render: (r) => <span className="small">{r.roles?.join(', ') ?? 'All roles'}</span> },
        ]}
      />
    </Card>
  )
}

function Contradictions() {
  const [obsolete, setObsolete] = useState(false)
  const q = useQuery(() => validation.contradictions(obsolete), [obsolete])
  return (
    <Card title={`${q.data?.count ?? '…'} places where documents disagree`} subtitle="When two documents conflict, the higher-priority one wins. This shows each case and why." actions={<label className="check small"><input type="checkbox" checked={obsolete} onChange={(e) => setObsolete(e.target.checked)} /> Include old versions</label>}>
      {q.loading ? <Spinner /> : (
        <Table
          rows={q.data?.contradictions}
          rowKey={(_, i) => String(i)}
          columns={[
            { key: 'detail', label: 'Conflict', render: (c) => <><div className="small">{c.detail}</div><div className="row gap-xs" style={{ marginTop: 4 }}><Badge value={c.kind} tone="warn" plain /><Badge value={c.category} tone="neutral" plain /></div></> },
            { key: 'winner', label: 'Wins', render: (c) => <span className="source">{c.winner.document_code} v{c.winner.version}</span> },
            { key: 'resolution', label: 'Why', render: (c) => <span className="small muted">{c.resolution}</span> },
          ]}
        />
      )}
    </Card>
  )
}
