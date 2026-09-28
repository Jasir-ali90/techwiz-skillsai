import type { Json } from '../api/client'
import { documents, org } from '../api/endpoints'
import { useQuery } from '../lib/hooks'

type Props = { value: string; onChange: (v: string) => void; allowEmpty?: string; className?: string }

export function EmployeeSelect({ value, onChange, allowEmpty }: Props) {
  const { data } = useQuery(async () => {
    const [employees, roles] = await Promise.all([org.employees(), org.roles()])
    const title = Object.fromEntries(roles.map((r: Json) => [r.id, r.title]))
    return employees.map((e: Json) => ({ ...e, role_title: title[e.job_role_id] }))
  })
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allowEmpty ?? 'Choose an employee…'}</option>
      {data?.map((e: Json) => (
        <option key={e.id} value={e.id}>
          {e.full_name} · {e.role_title} ({e.employee_code})
        </option>
      ))}
    </select>
  )
}

export function RoleSelect({ value, onChange, allowEmpty, exclude }: Props & { exclude?: string[] }) {
  const { data } = useQuery(() => org.roles())
  const roles = (data ?? []).filter((r: Json) => !exclude?.includes(r.code))
  if (data && exclude && !roles.length) return <div className="small muted">It already applies to every role.</div>
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allowEmpty ?? 'Choose a role…'}</option>
      {roles.map((r: Json) => (
        <option key={r.id} value={r.id}>
          {r.title}
        </option>
      ))}
    </select>
  )
}

export function DepartmentSelect({ value, onChange, allowEmpty }: Props) {
  const { data } = useQuery(() => org.departments())
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allowEmpty ?? 'Choose a department…'}</option>
      {data?.map((d: Json) => (
        <option key={d.id} value={d.id}>
          {d.name}
        </option>
      ))}
    </select>
  )
}

export function DocumentSelect({ value, onChange, allowEmpty, filter }: Props & { filter?: (d: Json) => boolean }) {
  const { data } = useQuery(() => documents.list())
  const docs = (data ?? []).filter(filter ?? (() => true))
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allowEmpty ?? 'Choose a document…'}</option>
      {docs.map((d: Json) => (
        <option key={d.id} value={d.id}>
          {d.document_code} v{d.version} · {d.title} ({d.status})
        </option>
      ))}
    </select>
  )
}

export const DOCUMENT_TYPES = [
  'HANDBOOK', 'HR_POLICY', 'LEAVE_POLICY', 'INFOSEC_POLICY', 'CONDUCT_POLICY', 'DATA_PRIVACY_POLICY',
  'DEPARTMENT_SOP', 'ROLE_DESCRIPTION', 'PROCESS_DOCUMENT', 'FAQ', 'COMPLIANCE_INSTRUCTION', 'ESCALATION_PROCEDURE',
]
export const REQUIREMENT_TYPES = ['MUST_KNOW', 'MUST_COMPLETE', 'MUST_DEMONSTRATE', 'MUST_ACKNOWLEDGE', 'RECOMMENDED', 'OPTIONAL', 'NOT_APPLICABLE']
export const PRIORITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
