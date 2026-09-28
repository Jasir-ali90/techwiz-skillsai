import { useState } from 'react'
import { ListOrdered, RotateCcw, Save, Scale } from 'lucide-react'
import type { Json } from '../api/client'
import { config, documents } from '../api/endpoints'
import { Alert, Badge, Button, Card, JsonEditor, KeyValue, PageHeader, Spinner, Table, humanize } from '../components/ui'
import { useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

export function ConfigPage() {
  const keys = useQuery(() => config.keys())
  const [key, setKey] = useState('precedence')
  return (
    <div className="stack">
      <PageHeader title="Configuration" subtitle="Advanced settings. Each one starts from a default file and can be changed here without touching code. Reset returns it to the default." />
      <div className="split">
        <Card title="Settings">
          <div className="list-nav">
            {keys.data?.map((k: Json) => (
              <button key={k.key} className={key === k.key ? 'active' : ''} onClick={() => setKey(k.key)}>
                {humanize(k.key)} {k.source === 'database' && <Badge value="Changed" tone="info" plain />}
              </button>
            ))}
          </div>
        </Card>
        <ConfigEditor key={key} configKey={key} onSaved={keys.reload} />
      </div>
    </div>
  )
}

function ConfigEditor({ configKey, onSaved }: { configKey: string; onSaved: () => void }) {
  const { can } = useAuth()
  const q = useQuery(() => config.get(configKey), [configKey])
  const [draft, setDraft] = useState<Json>(null)
  const [valid, setValid] = useState(true)
  const [version, setVersion] = useState(0)
  const save = useAction(() => config.put(configKey, draft ?? q.data.value), (r: Json) => `Saved (version ${r.version})`)
  const reset = useAction(() => config.reset(configKey), 'Reset to the default')
  const reapply = useAction(() => config.reapplyPrecedence(), (r: Json) => (r.documents_updated ? `${r.documents_updated} document priorities updated` : 'No document priorities needed changing'))
  if (!q.data) return <Spinner />
  const done = () => { q.reload(); onSaved(); setDraft(null); setVersion((v) => v + 1) }
  return (
    <div className="stack">
      <Card
        title={humanize(configKey)}
        actions={
          can('ADMIN') && (
            <>
              {q.data.source === 'database' && <Button variant="danger" icon={RotateCcw} loading={reset.running} onClick={async () => { await reset.run(); done() }}>Reset to default</Button>}
              <Button variant="primary" icon={Save} disabled={!valid || draft === null} loading={save.running} onClick={async () => { if (await save.run()) done() }}>Save changes</Button>
            </>
          )
        }
      >
        <div className="stack">
          <KeyValue items={[['Currently using', q.data.source === 'database' ? <Badge value="Your changes" tone="info" /> : <Badge value="Default file" tone="muted" />], ['Version', q.data.version], ['About', q.data.description]]} />
          <JsonEditor initial={q.data.value} resetKey={`${configKey}:${version}:${q.data.version}`} rows={24} onChange={(v, ok) => { setValid(ok); if (ok) setDraft(v) }} />
          {!can('ADMIN') && <Alert kind="info">You can look, but only administrators can save changes.</Alert>}
        </div>
      </Card>
      {configKey === 'precedence' && can('ADMIN') && (
        <Card title="Apply the new priority order" icon={ListOrdered} subtitle="After changing priorities, update existing documents. Then run step 4 on the Requirements page." actions={<Button icon={ListOrdered} loading={reapply.running} onClick={() => reapply.run()}>Update documents</Button>}>
          {reapply.result && <Table rows={(reapply.result as Json).changes} rowKey={(c) => `${c.document_code}${c.version}`} empty="Every document already had the right priority." columns={[{ key: 'document_code', label: 'Document' }, { key: 'version', label: 'Version' }, { key: 'old_rank', label: 'Was' }, { key: 'new_rank', label: 'Now' }]} />}
          <ResolveConflict />
        </Card>
      )}
    </div>
  )
}

function ResolveConflict() {
  const docs = useQuery(() => documents.list({ status_filter: 'ACTIVE' }))
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const resolve = useAction(() => config.resolvePrecedence([a, b]))
  const r = resolve.result as Json
  const opts = docs.data?.map((d: Json) => <option key={d.id} value={d.id}>{d.document_code} v{d.version} (priority {d.precedence_rank})</option>)
  return (
    <div className="stack-sm" style={{ marginTop: 16 }}>
      <div className="row gap-sm"><Scale size={16} className="muted" /><strong>Which document wins a conflict?</strong></div>
      <div className="row wrap gap-sm">
        <select className="input" style={{ maxWidth: 280 }} value={a} onChange={(e) => setA(e.target.value)}><option value="">First document…</option>{opts}</select>
        <select className="input" style={{ maxWidth: 280 }} value={b} onChange={(e) => setB(e.target.value)}><option value="">Second document…</option>{opts}</select>
        <Button disabled={!a || !b || a === b} loading={resolve.running} onClick={() => resolve.run()}>Compare</Button>
      </div>
      {r && <Alert kind="success"><strong>{r.winner.document_code}</strong> wins. {r.reason}</Alert>}
    </div>
  )
}
