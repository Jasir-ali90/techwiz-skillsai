import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, Building2, CalendarRange, Plus, Users } from 'lucide-react'
import type { Json } from '../api/client'
import { matrix, org } from '../api/endpoints'
import { DepartmentSelect, RoleSelect } from '../components/pickers'
import { Alert, Avatar, Badge, Button, Card, Field, Modal, PageHeader, Table, Tabs, fmtDay, humanize } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

export function OrganizationPage() {
  const [tab, setTab] = useState('employees')
  return (
    <div>
      <PageHeader title="Organization" subtitle="People, roles, departments and the onboarding schedule. Everything here can be changed without touching code." />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'employees', label: 'New hires', icon: Users }, { id: 'roles', label: 'Job roles', icon: Briefcase }, { id: 'stages', label: 'Schedule', icon: CalendarRange }, { id: 'departments', label: 'Departments', icon: Building2 }]} />
      {tab === 'employees' && <Employees />}
      {tab === 'roles' && <Roles />}
      {tab === 'stages' && <Stages />}
      {tab === 'departments' && <Departments />}
    </div>
  )
}

function Employees() {
  const { can } = useAuth()
  const list = useQuery(() => org.employees())
  const roles = useQuery(() => org.roles())
  const [editing, setEditing] = useState<Json | null>(null)
  const roleName = Object.fromEntries((roles.data ?? []).map((r: Json) => [r.id, r.title]))
  return (
    <Card title={`${list.data?.length ?? 0} new hires`} subtitle={can(...GENERATORS) ? 'Select someone to edit their details.' : undefined} actions={can(...GENERATORS) && <Button variant="primary" icon={Plus} onClick={() => setEditing({})}>Add new hire</Button>}>
      <Table
        rows={list.data}
        onRowClick={can(...GENERATORS) ? setEditing : undefined}
        columns={[
          { key: 'full_name', label: 'Name', render: (e) => <div className="row gap-sm"><Avatar name={e.full_name} /><div><div className="strong">{e.full_name}</div><div className="source">{e.employee_code}</div></div></div> },
          { key: 'role', label: 'Role', render: (e) => roleName[e.job_role_id] },
          { key: 'experience_level', label: 'Level', render: (e) => <Badge value={e.experience_level} tone="neutral" plain /> },
          { key: 'joining_date', label: 'Joined', render: (e) => <span className="small nowrap">{fmtDay(e.joining_date)}</span> },
          { key: 'training_status', label: 'Progress', render: (e) => <Badge value={e.training_status} /> },
          { key: 'links', label: '', render: (e) => <Link className="small" to={`/progress?employee=${e.id}`} onClick={(ev) => ev.stopPropagation()}>View progress</Link> },
        ]}
      />
      {editing && <EmployeeModal employee={editing} onClose={() => setEditing(null)} onDone={list.reload} />}
    </Card>
  )
}

function EmployeeModal({ employee, onClose, onDone }: { employee: Json; onClose: () => void; onDone: () => void }) {
  const isNew = !employee.id
  const [f, setF] = useState<Json>({ employee_code: '', full_name: '', job_role_id: '', department_id: '', experience_level: 'BEGINNER', joining_date: new Date().toISOString().slice(0, 10), location: '', previous_experience: '', ...employee, required_competencies: (employee.required_competencies ?? []).join(', ') })
  const save = useAction(async () => {
    const body = { ...f, required_competencies: String(f.required_competencies).split(',').map((s: string) => s.trim()).filter(Boolean) }
    for (const k of ['id', 'training_status', 'manager_id', 'user_id']) delete body[k]
    if (isNew) return org.createEmployee(body)
    delete body.employee_code
    delete body.joining_date
    return org.updateEmployee(employee.id, body)
  }, isNew ? 'New hire added' : 'Details saved')
  const set = (k: string, v: unknown) => setF({ ...f, [k]: v })
  return (
    <Modal open title={isNew ? 'Add a new hire' : `Edit ${employee.full_name}`} onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.running} onClick={async () => { if (await save.run()) { onDone(); onClose() } }}>Save</Button></>}>
      <div className="form-grid">
        <Field label="Employee code"><input className="input" disabled={!isNew} placeholder="EMP-011" value={f.employee_code} onChange={(e) => set('employee_code', e.target.value)} /></Field>
        <Field label="Full name"><input className="input" value={f.full_name} onChange={(e) => set('full_name', e.target.value)} /></Field>
        <Field label="Role"><RoleSelect value={f.job_role_id} onChange={(v) => set('job_role_id', v)} /></Field>
        <Field label="Department"><DepartmentSelect value={f.department_id} onChange={(v) => set('department_id', v)} /></Field>
        <Field label="Experience level"><select className="input" value={f.experience_level} onChange={(e) => set('experience_level', e.target.value)}>{['BEGINNER', 'INTERMEDIATE', 'ADVANCED'].map((l) => <option key={l} value={l}>{humanize(l)}</option>)}</select></Field>
        <Field label="Start date"><input className="input" type="date" disabled={!isNew} value={f.joining_date} onChange={(e) => set('joining_date', e.target.value)} /></Field>
        <Field label="Location"><input className="input" value={f.location ?? ''} onChange={(e) => set('location', e.target.value)} /></Field>
        <Field label="Skills they must build" hint="Separate with commas. Any not covered by a document will show as a gap."><input className="input" value={f.required_competencies} onChange={(e) => set('required_competencies', e.target.value)} /></Field>
      </div>
    </Modal>
  )
}

function Roles() {
  const { can } = useAuth()
  const list = useQuery(() => org.roles())
  const depts = useQuery(() => org.departments())
  const [f, setF] = useState({ code: '', title: '', department_id: '', description: '' })
  const create = useAction(async () => {
    const role = await org.createRole(f)
    const mapped = await matrix.mapRoles({ job_role_id: role.id })
    return { role, mapped }
  }, (r: Json) => `Role added with ${r.mapped.mappings_created} requirements`)
  const toggle = useAction((r: Json) => org.updateRole(r.id, { is_active: !r.is_active }), 'Role updated')
  const deptName = Object.fromEntries((depts.data ?? []).map((d: Json) => [d.id, d.name]))
  return (
    <div className="stack">
      {can('ADMIN') && (
        <Card title="Add a job role" subtitle="The new role is matched to the relevant requirements straight away.">
          <div className="form-grid">
            <Field label="Code"><input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} placeholder="ML_ENG" /></Field>
            <Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Machine Learning Engineer" /></Field>
            <Field label="Department"><DepartmentSelect value={f.department_id} onChange={(v) => setF({ ...f, department_id: v })} /></Field>
            <Field label="Description"><input className="input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          </div>
          <div style={{ marginTop: 12 }}><Button variant="primary" loading={create.running} disabled={!f.code || !f.title || !f.department_id} onClick={async () => { if (await create.run()) { list.reload(); setF({ code: '', title: '', department_id: '', description: '' }) } }}>Add role</Button></div>
          {create.result && <Alert kind="success">{(create.result as Json).role.title} now has {(create.result as Json).mapped.mappings_created} requirements. See them under Requirements, By role.</Alert>}
        </Card>
      )}
      <Card title={`${list.data?.length ?? 0} job roles`}>
        <Table rows={list.data} columns={[{ key: 'title', label: 'Role', render: (r) => <><div className="strong">{r.title}</div><div className="source">{r.code}</div></> }, { key: 'dept', label: 'Department', render: (r) => deptName[r.department_id] }, { key: 'is_active', label: 'Active', render: (r) => <Badge value={r.is_active ? 'Active' : 'Inactive'} tone={r.is_active ? 'good' : 'muted'} /> }, { key: 'a', label: '', render: (r) => can('ADMIN') && <Button size="sm" onClick={async () => { await toggle.run(r); list.reload() }}>{r.is_active ? 'Turn off' : 'Turn on'}</Button> }]} />
      </Card>
    </div>
  )
}

function Stages() {
  const { can } = useAuth()
  const list = useQuery(() => org.stages())
  const [edits, setEdits] = useState<Record<string, Json>>({})
  const save = useAction((s: Json) => org.updateStage(s.id, edits[s.id]), 'Stage updated')
  const [n, setN] = useState({ code: '', name: '', sequence: '', offset_days: '' })
  const create = useAction(() => org.createStage({ ...n, sequence: Number(n.sequence), offset_days: Number(n.offset_days) }), 'Stage added')
  return (
    <div className="stack">
      <Card title="Onboarding schedule" subtitle="Change the due day of a stage to make onboarding shorter or longer.">
        <Table
          rows={list.data}
          columns={[
            { key: 'sequence', label: 'Step', render: (s) => <span className="step-no">{s.sequence}</span> },
            { key: 'name', label: 'Name', render: (s) => (can('ADMIN') ? <input className="input" defaultValue={s.name} onChange={(e) => setEdits({ ...edits, [s.id]: { ...edits[s.id], name: e.target.value } })} /> : s.name) },
            { key: 'offset_days', label: 'Due on day', render: (s) => (can('ADMIN') ? <input className="input" style={{ width: 90 }} type="number" defaultValue={s.offset_days} onChange={(e) => setEdits({ ...edits, [s.id]: { ...edits[s.id], offset_days: Number(e.target.value) } })} /> : s.offset_days) },
            { key: 'is_active', label: 'Active', render: (s) => <Badge value={s.is_active ? 'Active' : 'Inactive'} tone={s.is_active ? 'good' : 'muted'} /> },
            { key: 'a', label: '', render: (s) => can('ADMIN') && <Button size="sm" disabled={!edits[s.id]} loading={save.running} onClick={async () => { await save.run(s); list.reload() }}>Save</Button> },
          ]}
        />
      </Card>
      {can('ADMIN') && (
        <Card title="Add a stage" subtitle="For example, a 120-day check-in.">
          <div className="form-grid">
            <Field label="Code"><input className="input" value={n.code} onChange={(e) => setN({ ...n, code: e.target.value.toUpperCase() })} placeholder="DAY_120" /></Field>
            <Field label="Name"><input className="input" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} /></Field>
            <Field label="Sequence"><input className="input" type="number" value={n.sequence} onChange={(e) => setN({ ...n, sequence: e.target.value })} /></Field>
            <Field label="Due on day"><input className="input" type="number" value={n.offset_days} onChange={(e) => setN({ ...n, offset_days: e.target.value })} /></Field>
          </div>
          <div style={{ marginTop: 12 }}><Button variant="primary" loading={create.running} disabled={!n.code || !n.name || !n.sequence} onClick={async () => { await create.run(); list.reload() }}>Add stage</Button></div>
        </Card>
      )}
    </div>
  )
}

function Departments() {
  const { can } = useAuth()
  const list = useQuery(() => org.departments())
  const [f, setF] = useState({ code: '', name: '', description: '' })
  const create = useAction(() => org.createDepartment(f), 'Department added')
  return (
    <div className="stack">
      <Card title={`${list.data?.length ?? 0} departments`}><Table rows={list.data} columns={[{ key: 'name', label: 'Department', render: (d) => <><div className="strong">{d.name}</div><div className="source">{d.code}</div></> }, { key: 'description', label: 'Description', render: (d) => <span className="small muted">{d.description}</span> }]} /></Card>
      {can('ADMIN') && (
        <Card title="Add a department">
          <div className="form-grid">
            <Field label="Code"><input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} /></Field>
            <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <Field label="Description"><input className="input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          </div>
          <div style={{ marginTop: 12 }}><Button variant="primary" loading={create.running} disabled={!f.code || !f.name} onClick={async () => { await create.run(); list.reload() }}>Add department</Button></div>
        </Card>
      )}
    </div>
  )
}
