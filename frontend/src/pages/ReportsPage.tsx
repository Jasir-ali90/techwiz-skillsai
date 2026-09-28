import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Download, FileBarChart, Search } from 'lucide-react'
import type { Json } from '../api/client'
import { reports, search } from '../api/endpoints'
import { DepartmentSelect, RoleSelect } from '../components/pickers'
import { Avatar, Badge, Button, Card, Field, KeyValue, PageHeader, Spinner, Table, Tabs, formatCell, humanize, pct } from '../components/ui'
import { useAction, useQuery } from '../lib/hooks'
import { org } from '../api/endpoints'

export function ReportsPage() {
  const [tab, setTab] = useState('reports')
  return (
    <div>
      <PageHeader title="Reports" subtitle="Ready-made reports you can download as CSV, Excel or PDF, and a search across every new hire's record." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'reports', label: 'Reports', icon: FileBarChart }, { id: 'records', label: 'Find records', icon: Search }]} />
      {tab === 'reports' ? <Reports /> : <Records />}
    </div>
  )
}

function Reports() {
  const list = useQuery(() => reports.list())
  const [active, setActive] = useState('comparison')
  const data = useQuery(() => reports.get(active), [active])
  const dl = useAction((format: string) => reports.download(active, format), 'Download started')
  const rows: Json[] = data.data?.rows ?? []
  const columns = rows.length ? Object.keys(rows[0]).filter((k) => typeof rows[0][k] !== 'object').slice(0, 9) : []
  return (
    <div className="split">
      <Card title="Reports">
        <div className="list-nav">
          {list.data?.map((r: Json) => (
            <button key={r.name} className={active === r.name ? 'active' : ''} onClick={() => setActive(r.name)}>
              {r.title}
            </button>
          ))}
        </div>
      </Card>
      <Card
        title={data.data?.title ?? active}
        actions={[['csv', 'CSV'], ['xlsx', 'Excel'], ['pdf', 'PDF']].map(([f, l]) => <Button key={f} size="sm" icon={Download} disabled={dl.running} onClick={() => dl.run(f)}>{l}</Button>)}
      >
        {data.loading ? <Spinner label="Building report…" /> : (
          <div className="stack">
            <KeyValue items={Object.entries(data.data?.summary ?? {}).map(([k, v]) => [humanize(k), formatCell(v)] as [string, ReactNode])} />
            <div className="muted small">{rows.length} row{rows.length === 1 ? '' : 's'}{rows.length > 200 ? '. The first 200 are shown; downloads include all.' : ''}</div>
            <Table rows={rows.slice(0, 200)} rowKey={(_, i) => String(i)} columns={columns.map((c) => ({ key: c, label: humanize(c) }))} />
          </div>
        )}
      </Card>
    </div>
  )
}

function Records() {
  const [f, setF] = useState<Json>({ employee: '', role: '', department: '', module: '', policy: '', status: '', verification: '', progress_min: '', progress_max: '', page: 1, page_size: 20 })
  const roles = useQuery(() => org.roles())
  const depts = useQuery(() => org.departments())
  const [roleId, setRoleId] = useState('')
  const [deptId, setDeptId] = useState('')
  const q = useQuery(() => search.records(f), [JSON.stringify(f)])
  const set = (k: string, v: unknown) => setF({ ...f, [k]: v, page: k === 'page' ? v : 1 })
  return (
    <div className="stack">
      <Card>
        <div className="form-grid">
          <Field label="New hire"><input className="input" value={f.employee} onChange={(e) => set('employee', e.target.value)} placeholder="Name or code" /></Field>
          <Field label="Role"><RoleSelect value={roleId} onChange={(v) => { setRoleId(v); set('role', roles.data?.find((r: Json) => r.id === v)?.code ?? '') }} allowEmpty="Any" /></Field>
          <Field label="Department"><DepartmentSelect value={deptId} onChange={(v) => { setDeptId(v); set('department', depts.data?.find((d: Json) => d.id === v)?.code ?? '') }} allowEmpty="Any" /></Field>
          <Field label="Module"><input className="input" value={f.module} onChange={(e) => set('module', e.target.value)} placeholder="e.g. release management" /></Field>
          <Field label="Policy cited"><input className="input" value={f.policy} onChange={(e) => set('policy', e.target.value)} placeholder="e.g. POL-INFOSEC-001" /></Field>
          <Field label="Progress status"><select className="input" value={f.status} onChange={(e) => set('status', e.target.value)}><option value="">Any</option>{['ON_TRACK', 'REQUIRES_ATTENTION', 'BEHIND_SCHEDULE', 'ASSESSMENT_REQUIRED', 'COMPLETED', 'NOT_STARTED'].map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</select></Field>
          <Field label="Plan check result"><select className="input" value={f.verification} onChange={(e) => set('verification', e.target.value)}><option value="">Any</option>{['VERIFIED', 'VERIFIED_WITH_WARNING', 'INCOMPLETE', 'UNSUPPORTED', 'CONTRADICTORY', 'MANUAL_REVIEW_REQUIRED'].map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</select></Field>
          <Field label="Progress between (%)"><div className="row gap-sm"><input className="input" type="number" min={0} max={100} placeholder="0" value={f.progress_min} onChange={(e) => set('progress_min', e.target.value)} /><input className="input" type="number" min={0} max={100} value={f.progress_max} placeholder="100" onChange={(e) => set('progress_max', e.target.value)} /></div></Field>
        </div>
      </Card>
      <Card title={q.loading && !q.data ? 'Searching…' : `${q.data?.total ?? 0} matching record${q.data?.total === 1 ? '' : 's'}`} actions={q.data && <div className="row gap-sm"><Button size="sm" icon={ChevronLeft} aria-label="Previous page" disabled={f.page <= 1} onClick={() => set('page', f.page - 1)} /><span className="small">page {q.data.page} of {Math.max(1, q.data.pages)}</span><Button size="sm" icon={ChevronRight} aria-label="Next page" disabled={f.page >= q.data.pages} onClick={() => set('page', f.page + 1)} /></div>}>
        <Table
          rows={q.data?.results}
          rowKey={(r) => r.employee_id}
          columns={[
            { key: 'name', label: 'New hire', render: (r) => <Link to={`/progress?employee=${r.employee_id}`} className="row gap-sm" style={{ color: 'inherit' }}><Avatar name={r.name} /><span><span className="strong" style={{ display: 'block' }}>{r.name}</span><span className="small subtle">{r.role} · {r.department}</span></span></Link> },
            { key: 'training_status', label: 'Progress status', render: (r) => <Badge value={r.training_status} /> },
            { key: 'overall_progress', label: 'Progress', render: (r) => pct(r.overall_progress) },
            { key: 'verification_status', label: 'Plan check', render: (r) => (r.plan_id ? <Link to={`/plans/${r.plan_id}`}><Badge value={r.verification_status} /></Link> : '—') },
            { key: 'matched_modules', label: 'Matching modules', render: (r) => <span className="small muted">{r.matched_modules?.slice(0, 3).join(', ') ?? '—'}</span> },
          ]}
        />
      </Card>
    </div>
  )
}
