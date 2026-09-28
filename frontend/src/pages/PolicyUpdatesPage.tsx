import { Link, useSearchParams } from 'react-router-dom'
import { Eye, RefreshCw, Search, Upload } from 'lucide-react'
import type { Json } from '../api/client'
import { impact } from '../api/endpoints'
import { DocumentSelect } from '../components/pickers'
import { Alert, Badge, Button, Card, Empty, KeyValue, PageHeader, Stat, Table, humanize } from '../components/ui'
import { useAction, useQuery } from '../lib/hooks'

export function PolicyUpdatesPage() {
  const [params, setParams] = useSearchParams()
  const docId = params.get('doc') ?? ''
  const existing = useQuery(() => (docId ? impact.get(docId).catch(() => null) : Promise.resolve(null)), [docId])
  const analyse = useAction(() => impact.analyse(docId), 'Changes found')
  const affected = useQuery(() => (docId && (analyse.result || existing.data) ? impact.affected(docId).catch(() => null) : Promise.resolve(null)), [docId, analyse.result, existing.data])
  const dry = useAction(() => impact.regenerate(docId, true))
  const apply = useAction(() => impact.regenerate(docId, false), 'Affected modules updated')
  const record: Json = analyse.result ?? existing.data
  return (
    <div className="stack">
      <PageHeader title="Policy updates" subtitle="When a policy changes, see exactly what changed, who it affects, and update only the parts of each plan that need it." />
      <Card title="1. Choose the updated document" subtitle="Only documents with an earlier version are listed." actions={<Link className="btn btn-sm btn-secondary" to="/documents"><Upload size={14} /> Upload a new version</Link>}>
        <div className="row wrap gap-sm">
          <div className="grow" style={{ minWidth: 280 }}>
            <DocumentSelect value={docId} onChange={(v) => { setParams(v ? { doc: v } : {}); analyse.setResult(undefined); dry.setResult(undefined); apply.setResult(undefined) }} filter={(d) => d.version > 1 && d.status === 'ACTIVE'} allowEmpty="Choose a document…" />
          </div>
          <Button variant="primary" icon={Search} disabled={!docId} loading={analyse.running} onClick={() => analyse.run()}>Find what changed</Button>
        </div>
      </Card>

      {record && (
        <>
          <Card title="2. What changed" subtitle={`${record.document_code}, version ${record.previous_version} compared with version ${record.new_version}. Old text on the left, new text on the right.`}>
            <div className="stack">
              <div className="grid grid-stats">
                <Stat label="Sections changed" value={record.diff.counts.modified} tone={record.diff.counts.modified ? 'warn' : undefined} />
                <Stat label="Sections added" value={record.diff.counts.added} />
                <Stat label="Sections removed" value={record.diff.counts.removed} />
                <Stat label="Unchanged" value={record.diff.counts.unchanged} />
              </div>
              {record.diff.modified.map((m: Json) => (
                <div key={m.section_id ?? m.heading} className="stack-sm">
                  <div className="row gap-sm"><strong>§{m.section_id ?? m.heading}</strong><span className="small">{m.summary}</span></div>
                  <div className="grid grid-2"><div className="diff-old small">{m.old_text}</div><div className="diff-new small">{m.new_text}</div></div>
                </div>
              ))}
              {record.diff.added.length > 0 && <div className="small"><strong>New sections:</strong> {record.diff.added.map((a: Json) => `§${a.section_id ?? a.heading}`).join(', ')}</div>}
            </div>
          </Card>

          <Card title="3. Who and what it affects">
            <div className="stack">
              <div className="grid grid-stats">
                <Stat label="Requirements" value={record.affected_requirement_codes.length} />
                {Object.entries(record.affected_items).map(([k, v]) => <Stat key={k} label={humanize(k)} value={String(v)} />)}
                <Stat label="Plans" value={record.affected_plan_ids.length} />
                <Stat label="New hires" value={record.affected_employee_ids.length} />
              </div>
              <p className="muted small" style={{ margin: 0 }}>Items that cite unchanged sections just have their reference moved to the new version: {Object.entries(record.reference_only_items).map(([k, v]) => `${v} ${humanize(k).toLowerCase()}`).join(', ') || 'none'}.</p>
              {affected.data && (
                <>
                  <Table rows={affected.data.requirements} rowKey={(r) => r.requirement_code} columns={[{ key: 'statement', label: 'Requirement', render: (r) => <><div className="small">{r.statement}</div><div className="source">{r.requirement_code} · §{r.section}</div></> }, { key: 'document_version', label: 'Now from', render: (r) => `v${r.document_version}` }]} />
                  <Table rows={affected.data.plans} columns={[{ key: 'title', label: 'Plan', render: (p) => <Link to={`/plans/${p.id}`}>{p.title}</Link> }, { key: 'verification_status', label: 'Check result', render: (p) => <Badge value={p.verification_status} /> }]} />
                </>
              )}
            </div>
          </Card>

          <Card title="4. Update the plans" subtitle="Only the affected modules are rewritten. Progress on everything else is kept." actions={<><Button icon={Eye} loading={dry.running} onClick={() => dry.run()}>Preview changes</Button><Button variant="primary" icon={RefreshCw} loading={apply.running} onClick={() => apply.run()}>Update affected modules</Button></>}>
            {apply.running && (
              <Alert kind="info">
                Updating {record.affected_plan_ids.length} plan{record.affected_plan_ids.length === 1 ? '' : 's'}: each one is rewritten and then checked again, which takes
                about 15 seconds per plan (longer with a local AI model). You can leave this page open; the result appears here.
              </Alert>
            )}
            {!dry.result && !apply.result && !apply.running && <Empty icon={Eye} title="Preview first">See exactly which modules would be rewritten before changing anything.</Empty>}
            {dry.result && !apply.result && (
              <div className="stack">
                <KeyValue items={[['Sections to re-read', dry.result.would_change.re_extract_sections.join(', ') || 'None'], ['Requirements to update', dry.result.would_change.requirements_updated.join(', ') || 'None'], ['New requirements', dry.result.would_change.requirements_new.length], ['References to move', Object.entries(dry.result.would_change.references_repointed ?? {}).map(([k, v]) => `${v} ${humanize(k).toLowerCase()}`).join(', ') || 'None']]} />
                <Table rows={dry.result.would_change.plans} rowKey={(p) => p.plan_id} columns={[{ key: 'title', label: 'Plan', render: (p) => <span className="strong small">{p.title}</span> }, { key: 'r', label: 'Modules to rewrite', render: (p) => <span className="small">{p.modules_to_regenerate.map((m: Json) => m.title).join(', ')}</span> }, { key: 'k', label: 'Kept', render: (p) => `${p.modules_preserved.length} unchanged` }]} />
              </div>
            )}
            {apply.result && (
              <div className="stack">
                <Alert kind="success">Plans updated. {apply.result.extraction.updated} requirements changed, {apply.result.extraction.created} added and {apply.result.references_repointed} references moved to the new version.</Alert>
                <Table rows={apply.result.plans} rowKey={(p) => p.plan_id} columns={[{ key: 'plan', label: 'Plan', render: (p) => <Link to={`/plans/${p.plan_id}`}>Open plan</Link> }, { key: 'modules_replaced', label: 'Rewritten', render: (p) => <span className="small">{p.failed ? <span className="bad">Not updated: {p.failed}</span> : (p.modules_replaced ?? []).join(', ') || p.skipped}</span> }, { key: 'kept', label: 'Kept', render: (p) => `${(p.modules_preserved ?? []).length}` }, { key: 'verification_status', label: 'Check result', render: (p) => <Badge value={p.verification_status} /> }]} />
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
