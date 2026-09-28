import { useState } from 'react'
import { CheckCircle2, GitBranch, LayoutGrid, List, ListChecks, Scale, Users } from 'lucide-react'
import type { Json } from '../api/client'
import { matrix } from '../api/endpoints'
import { PRIORITIES, REQUIREMENT_TYPES, RoleSelect } from '../components/pickers'
import { Alert, Badge, Button, Card, Empty, Field, JsonView, KeyValue, Modal, PageHeader, Spinner, Stat, Table, Tabs, humanize } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

export function MatrixPage() {
  const [tab, setTab] = useState('build')
  const [code, setCode] = useState<string | null>(null)
  return (
    <div>
      <PageHeader title="Requirements" subtitle="Everything each role must learn, read from company documents by fixed rules. Every plan is checked against this list, so the AI never marks its own work." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'build', label: 'Summary', icon: LayoutGrid }, { id: 'role', label: 'By role', icon: Users }, { id: 'requirements', label: 'All requirements', icon: List }]} />
      {tab === 'build' && <BuildPanel />}
      {tab === 'role' && <RoleMatrix onOpen={setCode} />}
      {tab === 'requirements' && <Requirements onOpen={setCode} />}
      {code && <RequirementModal code={code} onClose={() => setCode(null)} />}
    </div>
  )
}

function BuildPanel() {
  const { can } = useAuth()
  const summary = useQuery(() => matrix.summary())
  const extract = useAction(() => matrix.extract({}), (r: Json) => `${r.requirements_found} requirements (${r.created} new)`)
  const map = useAction(() => matrix.mapRoles({}), (r: Json) => `${r.mappings_created} role mappings`)
  const prereq = useAction(() => matrix.prerequisites(), (r: Json) => `${r.edge_count} prerequisite edges`)
  const conflicts = useAction(() => matrix.resolveConflicts(), (r: Json) => `${r.overridden_count} requirements overridden by precedence`)
  const s = summary.data
  const after = (fn: () => Promise<unknown>) => async () => { await fn(); summary.reload() }
  const last = conflicts.result ?? prereq.result ?? map.result ?? extract.result
  const steps = [
    { n: 1, icon: ListChecks, label: 'Find requirements', hint: 'Read every active document', a: extract },
    { n: 2, icon: Users, label: 'Match to roles', hint: 'Decide who each one applies to', a: map },
    { n: 3, icon: GitBranch, label: 'Set the order', hint: 'What must be learned first', a: prereq },
    { n: 4, icon: Scale, label: 'Resolve conflicts', hint: 'Higher-priority documents win', a: conflicts },
  ]
  return (
    <div className="stack">
      {s ? (
        <div className="grid grid-stats">
          {Object.entries(s.srs_minimums).map(([k, v]: [string, Json]) => <Stat key={k} label={humanize(k)} value={v.actual} tone={v.met ? 'good' : 'bad'} hint={v.met ? `Target of ${v.required} met` : `Below the target of ${v.required}`} />)}
          <Stat label="Optional or recommended" value={s.optional_or_recommended} />
          <Stat label="Replaced by a higher-priority document" value={s.overridden_by_precedence} />
          <Stat label="Not matched to any role" value={s.unmapped} tone={s.unmapped ? 'warn' : 'good'} hint={s.unmapped ? 'Check these' : 'All matched'} />
        </div>
      ) : <Spinner />}
      {can(...GENERATORS) && (
        <Card title="Rebuild the list" subtitle="Run these four steps in order after adding or changing documents.">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
            {steps.map((st) => (
              <button key={st.n} className="demo" style={{ alignItems: 'flex-start', padding: 14 }} disabled={st.a.running} onClick={after(() => st.a.run())}>
                <span className={`step-no ${st.a.result ? 'done' : ''}`}>{st.a.running ? <span className="spinner spinner-sm" /> : st.a.result ? <CheckCircle2 size={15} /> : st.n}</span>
                <span>
                  <span className="demo-name" style={{ display: 'block' }}>{st.label}</span>
                  <span className="demo-desc">{st.hint}</span>
                </span>
              </button>
            ))}
          </div>
          {last && <div style={{ marginTop: 12 }}><JsonView value={last} collapsed label="details of the last step" /></div>}
          {prereq.result?.cycles_rejected?.length > 0 && <div style={{ marginTop: 12 }}><Alert kind="warn">{prereq.result.cycles_rejected.length} circular order(s) were ignored: {prereq.result.cycles_rejected.map((c: Json) => c.cycle.join(' → ')).join('; ')}</Alert></div>}
        </Card>
      )}
      {s && (
        <div className="grid grid-2">
          <Card title="By role">
            <Table rows={s.per_role} rowKey={(r) => r.role_code} columns={[{ key: 'role_title', label: 'Role', render: (r) => <span className="strong">{r.role_title}</span> }, { key: 'requirements', label: 'Requirements' }, { key: 'mandatory', label: 'Mandatory' }]} />
          </Card>
          <Card title="By kind and document">
            <div className="stack">
              <div className="row wrap gap-xs">{Object.entries(s.per_type).map(([k, v]) => <span key={k} className="chip">{humanize(k)} <strong>{String(v)}</strong></span>)}</div>
              <Table rows={Object.entries(s.per_document).map(([doc, n]) => ({ doc, n }))} rowKey={(r) => r.doc} columns={[{ key: 'doc', label: 'Document', render: (r) => <span className="source">{r.doc}</span> }, { key: 'n', label: 'Requirements' }]} />
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

function RoleMatrix({ onOpen }: { onOpen: (code: string) => void }) {
  const [roleId, setRoleId] = useState('')
  const [onlyMandatory, setOnlyMandatory] = useState(false)
  const q = useQuery(() => (roleId ? matrix.role(roleId) : Promise.resolve(null)), [roleId])
  const rows = (q.data?.requirements ?? []).filter((r: Json) => !onlyMandatory || r.is_mandatory)
  return (
    <Card title={q.data ? q.data.role_title : 'Requirements for a role'} subtitle={q.data ? `${q.data.total} requirements, ${q.data.mandatory} of them mandatory. Select one to see why it applies.` : undefined} actions={<><div style={{ width: 240 }}><RoleSelect value={roleId} onChange={setRoleId} /></div><label className="check small nowrap"><input type="checkbox" checked={onlyMandatory} onChange={(e) => setOnlyMandatory(e.target.checked)} /> Mandatory only</label></>}>
      {!roleId && <Empty icon={Users} title="Choose a role">Pick a role above to see everything it must cover.</Empty>}
      {roleId && (
        <Table
          rows={rows}
          rowKey={(r) => r.requirement_code}
          onRowClick={(r) => onOpen(r.requirement_code)}
          columns={[
            { key: 'statement', label: 'Requirement', render: (r) => <><div className="small">{r.statement}</div><div className="source">{r.requirement_code}</div></> },
            { key: 'requirement_type', label: 'Type', render: (r) => <span className="small">{humanize(r.requirement_type)}</span> },
            { key: 'priority', label: 'Priority', render: (r) => <Badge value={r.priority} /> },
            { key: 'competency', label: 'Competency', render: (r) => <span className="small">{r.competency}</span> },
            { key: 'src', label: 'Source', render: (r) => <span className="source">{r.source_document_code} §{r.source_section_id}</span> },
            { key: 'mapping_method', label: 'Why it applies', render: (r) => <span className="small" title={r.mapping_reason}><Badge value={r.mapping_method} tone="neutral" plain /></span> },
            { key: 'prerequisites', label: 'Needs first', render: (r) => r.prerequisites.join(', ') || '—' },
          ]}
        />
      )}
    </Card>
  )
}

function Requirements({ onOpen }: { onOpen: (code: string) => void }) {
  const [f, setF] = useState({ requirement_type: '', priority: '', is_mandatory: '', job_role_id: '', include_inactive: false })
  const q = useQuery(() => matrix.requirements(f), [JSON.stringify(f)])
  return (
    <Card
      title={`${q.data?.length ?? 0} requirements`}
      actions={
        <>
          <select className="input" value={f.requirement_type} onChange={(e) => setF({ ...f, requirement_type: e.target.value })}><option value="">Any type</option>{REQUIREMENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select>
          <select className="input" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option value="">Any priority</option>{PRIORITIES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select>
          <select className="input" value={f.is_mandatory} onChange={(e) => setF({ ...f, is_mandatory: e.target.value })}><option value="">Mandatory or optional</option><option value="true">Mandatory</option><option value="false">Optional</option></select>
          <div style={{ width: 200 }}><RoleSelect value={f.job_role_id} onChange={(v) => setF({ ...f, job_role_id: v })} allowEmpty="Any role" /></div>
          <label className="check small nowrap"><input type="checkbox" checked={f.include_inactive} onChange={(e) => setF({ ...f, include_inactive: e.target.checked })} /> Include inactive</label>
        </>
      }
    >
      <Table
        rows={q.data}
        rowKey={(r) => r.requirement_code}
        onRowClick={(r) => onOpen(r.requirement_code)}
        columns={[
          { key: 'statement', label: 'Requirement', render: (r) => <><div className="small">{r.statement}</div><div className="source">{r.requirement_code}</div></> },
          { key: 'requirement_type', label: 'Type', render: (r) => <span className="small">{humanize(r.requirement_type)}</span> },
          { key: 'priority', label: 'Priority', render: (r) => <Badge value={r.priority} /> },
          { key: 'src', label: 'Source', render: (r) => <span className="source">{r.source_document_code} §{r.source_section_id}</span> },
          { key: 'flags', label: 'Flags', render: (r) => <div className="row wrap gap-sm">{r.override_reason && <Badge value="Replaced" tone="muted" />}{r.manually_overridden && <Badge value="Edited by hand" tone="info" />}{!r.is_active && <Badge value="Inactive" tone="muted" />}</div> },
        ]}
      />
    </Card>
  )
}

function RequirementModal({ code, onClose }: { code: string; onClose: () => void }) {
  const { can } = useAuth()
  const q = useQuery(() => matrix.requirement(code), [code])
  const [edit, setEdit] = useState<Json>({})
  const [roleId, setRoleId] = useState('')
  const [mapReason, setMapReason] = useState('')
  const patch = useAction(() => matrix.patchRequirement(code, edit), 'Requirement updated and logged')
  const addMap = useAction(() => matrix.addRoleMapping(code, { job_role_id: roleId, reason: mapReason }), 'Role added')
  const r = q.data
  return (
    <Modal open wide title={`Requirement ${code}`} onClose={onClose}>
      {!r ? <Spinner /> : (
        <div className="stack">
          <p className="quote">{r.statement}</p>
          <div className="grid grid-2">
            <KeyValue items={[['Kind', humanize(r.requirement_type)], ['Mandatory', r.is_mandatory ? 'Yes' : 'No'], ['Priority', <Badge value={r.priority} />], ['Competency', r.competency], ['Deadline', r.deadline_days ? `${r.deadline_days} days from joining` : '—'], ['Assessment', r.assessment_required ? r.assessment_topic : 'Not required']]} />
            <KeyValue items={[['Source', `${r.source_document?.document_code} v${r.source_document?.version} §${r.source_section_id}`], ['Chunk', <span className="source">{r.source_chunk_code}</span>], ['Found by', <span className="small">{humanize(r.extraction_method)} ({Math.round(r.extraction_confidence * 100)}% confident)</span>], ['Conditions', Object.keys(r.conditions ?? {}).length ? JSON.stringify(r.conditions) : '—'], ['Replaced because', r.override_reason ?? '—']]} />
          </div>
          <Card title={`Applies to ${r.mapped_roles.length} role${r.mapped_roles.length === 1 ? '' : 's'}`}>
            <Table rows={r.mapped_roles} rowKey={(m) => m.role_code} columns={[{ key: 'role_title', label: 'Role' }, { key: 'method', label: 'How', render: (m) => <Badge value={m.method} tone="neutral" plain /> }, { key: 'reason', label: 'Reason', render: (m) => <span className="small">{m.reason}</span> }, { key: 'priority_for_role', label: 'Priority', render: (m) => <Badge value={m.priority_for_role} /> }]} />
          </Card>
          {r.prerequisites.length > 0 && <div className="small"><strong>Prerequisites:</strong> {r.prerequisites.map((p: Json) => `${p.depends_on} (${p.reason})`).join('; ')}</div>}
          {r.source_chunk && <div className="small"><strong>Source text:</strong><p className="quote">{r.source_chunk.content}</p></div>}
          {can('ADMIN') && (
            <div className="grid grid-2">
              <Card title="Correct this requirement">
                <div className="stack-sm">
                  <div className="form-grid">
                    <Field label="Type"><select className="input" defaultValue="" onChange={(e) => setEdit({ ...edit, requirement_type: e.target.value || undefined })}><option value="">No change</option>{REQUIREMENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select></Field>
                    <Field label="Priority"><select className="input" defaultValue="" onChange={(e) => setEdit({ ...edit, priority: e.target.value || undefined })}><option value="">No change</option>{PRIORITIES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select></Field>
                  </div>
                  <Field label="Competency"><input className="input" placeholder={r.competency} onChange={(e) => setEdit({ ...edit, competency: e.target.value || undefined })} /></Field>
                  <Field label="Reason"><input className="input" onChange={(e) => setEdit({ ...edit, reason: e.target.value })} /></Field>
                  <Button variant="primary" loading={patch.running} onClick={async () => { await patch.run(); q.reload() }}>Save changes</Button>
                </div>
              </Card>
              <Card title="Apply it to another role">
                <div className="stack-sm">
                  <RoleSelect value={roleId} onChange={setRoleId} exclude={r.mapped_roles.map((m: Json) => m.role_code)} />
                  <Field label="Why it applies"><input className="input" value={mapReason} onChange={(e) => setMapReason(e.target.value)} /></Field>
                  <Button loading={addMap.running} disabled={!roleId || mapReason.length < 3} onClick={async () => { await addMap.run(); q.reload() }}>Add role</Button>
                </div>
              </Card>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
