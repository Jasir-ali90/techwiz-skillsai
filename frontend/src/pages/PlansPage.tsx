import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, BookOpen, CheckCircle2, ClipboardList, FileCode2, GitCompare, PenLine, Search, ShieldCheck, Wand2 } from 'lucide-react'
import type { Json } from '../api/client'
import { genai, org, plans } from '../api/endpoints'
import { EmployeeSelect, RoleSelect } from '../components/pickers'
import { Alert, Avatar, Badge, Button, Card, Empty, Field, KeyValue, PageHeader, Stat, Table, Tabs, fmtDate, humanize, pct } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

const STATUSES = ['VERIFIED', 'VERIFIED_WITH_WARNING', 'INCOMPLETE', 'UNSUPPORTED', 'CONTRADICTORY', 'MANUAL_REVIEW_REQUIRED']

export function PlansPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'plans'
  const setTab = (t: string) => setParams(t === 'plans' ? {} : { tab: t }, { replace: true })
  const { can } = useAuth()
  return (
    <div>
      <PageHeader
        title="Training plans"
        subtitle="Each plan is written by AI from company documents, then checked automatically against the requirement matrix."
        actions={can(...GENERATORS) && tab !== 'generate' && <Button variant="primary" icon={Wand2} onClick={() => setTab('generate')}>Create a plan</Button>}
      />
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'plans', label: 'All plans', icon: ClipboardList },
          ...(can(...GENERATORS) ? [{ id: 'generate', label: 'Create a plan', icon: Wand2 }] : []),
          { id: 'compare', label: 'Compare', icon: GitCompare },
          { id: 'prompts', label: 'Prompt templates', icon: FileCode2 },
        ]}
      />
      {tab === 'plans' && <PlanList />}
      {tab === 'generate' && <GeneratePanel />}
      {tab === 'compare' && <ComparePanel />}
      {tab === 'prompts' && <PromptTemplates />}
    </div>
  )
}

function PlanList() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ job_role_id: '', verification_status: '', current_only: true })
  const [text, setText] = useState('')
  const list = useQuery(() => plans.list(filters), [JSON.stringify(filters)])
  const roles = useQuery(() => org.roles())
  const employees = useQuery(() => org.employees())
  const roleName = Object.fromEntries((roles.data ?? []).map((r: Json) => [r.id, r.title]))
  const emp = Object.fromEntries((employees.data ?? []).map((e: Json) => [e.id, e]))
  const q = text.trim().toLowerCase()
  const rows = (list.data ?? []).filter((r: Json) => !q || `${r.title} ${emp[r.employee_id]?.full_name ?? ''}`.toLowerCase().includes(q))
  return (
    <Card
      title={`${rows.length} plan${rows.length === 1 ? '' : 's'}`}
      actions={
        <>
          <div className="search-input" style={{ width: 220 }}>
            <Search size={15} />
            <input className="input" placeholder="Search by name" value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div style={{ width: 200 }}><RoleSelect value={filters.job_role_id} onChange={(v) => setFilters({ ...filters, job_role_id: v })} allowEmpty="All roles" /></div>
          <select className="input" style={{ width: 190 }} value={filters.verification_status} onChange={(e) => setFilters({ ...filters, verification_status: e.target.value })}>
            <option value="">Any status</option>
            {STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
          </select>
          <label className="check small nowrap">
            <input type="checkbox" checked={filters.current_only} onChange={(e) => setFilters({ ...filters, current_only: e.target.checked })} /> Current only
          </label>
        </>
      }
    >
      <Table
        rows={list.loading && !list.data ? undefined : rows}
        empty={list.loading ? 'Loading plans…' : 'No plans match these filters.'}
        onRowClick={(r) => navigate(`/plans/${r.id}`)}
        columns={[
          {
            key: 'employee', label: 'New hire',
            render: (r) => (
              <div className="row gap-sm">
                <Avatar name={emp[r.employee_id]?.full_name} />
                <div>
                  <div className="strong">{emp[r.employee_id]?.full_name ?? '—'}</div>
                  <div className="small subtle">{roleName[r.job_role_id]}</div>
                </div>
              </div>
            ),
          },
          { key: 'verification_status', label: 'Check result', render: (r) => <Badge value={r.verification_status} /> },
          { key: 'gaps', label: 'Gaps', render: (r) => (r.gaps?.length ? <Badge value={`${r.gaps.length} gap${r.gaps.length > 1 ? 's' : ''}`} tone="warn" /> : <span className="subtle">None</span>) },
          { key: 'provider', label: 'Written by', render: (r) => <span className="small muted">{humanize(r.provider)}</span> },
          { key: 'generated_at', label: 'Created', render: (r) => <span className="small muted nowrap">{fmtDate(r.generated_at)}</span> },
          { key: 'is_current', label: 'Version', render: (r) => (r.is_current ? <Badge value="Current" tone="good" /> : <Badge value={r.status} />) },
        ]}
      />
    </Card>
  )
}

const STEPS = [
  { icon: BookOpen, label: 'Finding the right documents' },
  { icon: PenLine, label: 'Writing the plan' },
  { icon: ShieldCheck, label: 'Checking it against the requirements' },
]

function GeneratingSteps() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 3500)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="stack-sm" aria-live="polite">
      {STEPS.map((s, i) => (
        <div key={s.label} className={`row gap-sm ${i > step ? 'subtle' : ''}`}>
          {i < step ? <CheckCircle2 size={18} className="good" /> : i === step ? <span className="spinner" /> : <s.icon size={18} />}
          <span className={i === step ? 'strong' : ''}>{s.label}</span>
        </div>
      ))}
      <p className="small muted" style={{ marginTop: 12 }}>This usually takes 10–40 seconds.</p>
    </div>
  )
}

function GeneratePanel() {
  const [employeeId, setEmployeeId] = useState('')
  const [topics, setTopics] = useState('')
  const [promptVersion, setPromptVersion] = useState('')
  const [malformed, setMalformed] = useState(0)
  const [advanced, setAdvanced] = useState(false)
  const status = useQuery(() => genai.status())
  const [elapsed, setElapsed] = useState<number | null>(null)
  const gen = useAction(async () => {
    const started = performance.now()
    try {
      const plan = await plans.generate({
        employee_id: employeeId,
        prompt_version: promptVersion || undefined,
        extra_topics: topics.split('\n').map((t) => t.trim()).filter(Boolean),
        simulate_malformed: malformed,
        validate_after: true,
      })
      const run = await plans.generationRun(plan.id)
      return { plan, run: run.latest }
    } finally {
      setElapsed((performance.now() - started) / 1000)
    }
  }, 'Plan created and checked')

  const result = gen.result as Json
  const errorAttempts: Json[] = gen.error?.details?.attempts ?? []
  const ready = status.data?.chain.filter((p: Json) => p.usable) ?? []
  return (
    <div className="grid grid-2" style={{ alignItems: 'start' }}>
      <Card title="Who is the plan for?" subtitle="The plan is tailored to their role, department and experience.">
        <div className="stack">
          <Field label="New hire">
            <EmployeeSelect value={employeeId} onChange={setEmployeeId} />
          </Field>
          <Field label="Anything extra to cover?" hint="Optional, one topic per line. If no company document covers a topic, it's listed as a gap rather than made up.">
            <textarea className="input" rows={3} value={topics} onChange={(e) => setTopics(e.target.value)} placeholder={'e.g. Kubernetes cost optimisation\nCompany pet insurance'} />
          </Field>
          <button className="link small" onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}>
            {advanced ? 'Hide' : 'Show'} advanced options
          </button>
          {advanced && (
            <div className="form-grid">
              <Field label="Prompt version" hint="Leave blank for the default">
                <input className="input" value={promptVersion} onChange={(e) => setPromptVersion(e.target.value)} placeholder="v1" />
              </Field>
              <Field label="Simulate bad AI replies" hint="Demo only: shows the 3-try limit">
                <select className="input" value={malformed} onChange={(e) => setMalformed(Number(e.target.value))}>
                  {[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n === 0 ? 'Off' : `First ${n} ${n === 1 ? 'reply' : 'replies'}`}</option>)}
                </select>
              </Field>
            </div>
          )}
          <Button variant="primary" size="lg" icon={Wand2} block disabled={!employeeId} loading={gen.running} onClick={() => gen.run()}>
            {gen.running ? 'Creating plan…' : 'Create and check plan'}
          </Button>
          {status.data && (
            <div className="small muted">
              AI service: <strong>{ready.length ? humanize(ready[0].provider) : 'none ready'}</strong>
              {ready.length > 1 && `, with ${ready.slice(1).map((p: Json) => humanize(p.provider)).join(' and ')} as backup`}. <Link to="/ai">Change</Link>
            </div>
          )}
        </div>
      </Card>

      <Card title="Result">
        {gen.running && <GeneratingSteps />}
        {!gen.running && !result && !gen.error && (
          <Empty icon={ClipboardList} title="No plan yet">Choose a new hire and select "Create and check plan". You'll see which AI service wrote it, how many tries it took and how it scored.</Empty>
        )}
        {!gen.running && gen.error && (
          <div className="stack-sm">
            <Alert kind="error"><strong>The plan couldn't be created.</strong> {gen.error.message}</Alert>
            {errorAttempts.length > 0 && <Attempts attempts={errorAttempts} />}
          </div>
        )}
        {!gen.running && result && (
          <div className="stack">
            <div className="row between gap wrap">
              <div>
                <div className="small muted">Check result</div>
                <div style={{ marginTop: 4 }}><Badge value={result.plan.validation?.verification_status} /></div>
              </div>
              <Link className="btn btn-primary btn-md" to={`/plans/${result.plan.id}`}>Open plan <ArrowRight size={16} /></Link>
            </div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
              <Stat label="Modules" value={result.plan.counts.modules} />
              <Stat label="Tasks" value={result.plan.counts.tasks} />
              <Stat label="Mandatory covered" value={pct(result.plan.validation?.metrics?.mandatory_requirement_coverage_score)} />
            </div>
            <KeyValue
              items={[
                ['Written by', <>{humanize(result.run.provider)} <span className="source">{result.run.model}</span> {result.run.parameters?.fell_back && <Badge value="Backup service used" tone="warn" />}</>],
                ['Tries needed', result.run.attempt_count],
                ['Time taken', `${elapsed?.toFixed(1)} s`],
                ['Quiz questions', result.plan.counts.quiz_questions],
              ]}
            />
            {result.plan.gaps.length > 0 && (
              <div className="stack-sm">
                <Alert kind="warn"><strong>{result.plan.gaps.length} topic{result.plan.gaps.length > 1 ? 's' : ''} not covered.</strong> No company document supports {result.plan.gaps.length > 1 ? 'them' : 'it'}, so nothing was made up.</Alert>
                {result.plan.gaps.map((g: Json, i: number) => (
                  <div key={i} className="quote small"><strong>{g.topic}</strong>: {g.reason}</div>
                ))}
              </div>
            )}
            <details>
              <summary className="link small" style={{ cursor: 'pointer' }}>Show each AI try</summary>
              <div style={{ marginTop: 10 }}><Attempts attempts={result.run.attempts} /></div>
            </details>
          </div>
        )}
      </Card>
    </div>
  )
}

export function Attempts({ attempts }: { attempts: Json[] }) {
  return (
    <Table
      rows={attempts}
      rowKey={(_, i) => String(i)}
      columns={[
        { key: 'attempt', label: 'Try', width: '50px' },
        { key: 'provider', label: 'Service', render: (a) => humanize(a.provider ?? '—') },
        { key: 'status', label: 'Outcome', render: (a) => <Badge value={a.status === 'ok' ? 'SUCCEEDED' : a.status} tone={a.status === 'ok' ? 'good' : a.status === 'permanent_failure' ? 'bad' : 'warn'} /> },
        { key: 'kind', label: 'Reason', render: (a) => (a.kind ? humanize(a.kind) : '—') },
        { key: 'error', label: 'Detail', render: (a) => <span className="small clamp muted">{a.error ?? '—'}</span> },
        { key: 'duration_ms', label: 'Time', render: (a) => <span className="small nowrap">{a.duration_ms} ms</span> },
      ]}
    />
  )
}

function ComparePanel() {
  const [dimension, setDimension] = useState('role')
  const cmp = useQuery(() => plans.compare({ dimension }), [dimension])
  return (
    <div className="stack">
      <Card
        title="How plans differ"
        subtitle="Group plans to compare their size and coverage"
        actions={
          <select className="input" style={{ width: 200 }} value={dimension} onChange={(e) => setDimension(e.target.value)}>
            {['role', 'department', 'experience_level', 'document_version', 'plan'].map((d) => <option key={d} value={d}>By {humanize(d).toLowerCase()}</option>)}
          </select>
        }
      >
        <Table
          rows={cmp.data?.groups}
          rowKey={(r) => r.group}
          columns={[
            { key: 'group', label: 'Group', render: (r) => <strong>{r.group}</strong> },
            { key: 'plans', label: 'Plans' },
            { key: 'average_modules', label: 'Avg modules' },
            { key: 'requirements_covered', label: 'Requirements' },
            { key: 'average_coverage', label: 'Avg coverage', render: (r) => pct(r.average_coverage) },
            { key: 'verification_statuses', label: 'Check results', render: (r) => <div className="row wrap gap-xs">{Object.entries(r.verification_statuses).map(([k, v]) => <Badge key={k} value={`${humanize(k)} · ${v}`} tone={k === 'VERIFIED' ? 'good' : 'warn'} />)}</div> },
          ]}
        />
      </Card>
      <Card title="Side-by-side differences" subtitle="Requirements that appear in one group but not the other">
        <Table
          rows={cmp.data?.pairwise}
          rowKey={(r) => `${r.a}|${r.b}`}
          columns={[
            { key: 'pair', label: 'Compared', render: (r) => <span className="small strong">{r.a} <span className="subtle">vs</span> {r.b}</span> },
            { key: 'requirement_overlap', label: 'Shared', render: (r) => `${Math.round(r.requirement_overlap * 100)}%` },
            { key: 'only_in_a', label: 'Only in first', render: (r) => <span className="small">{r.only_in_a.length} items <span className="muted">· {r.categories_only_in_a.slice(0, 3).join(', ')}</span></span> },
            { key: 'only_in_b', label: 'Only in second', render: (r) => <span className="small">{r.only_in_b.length} items <span className="muted">· {r.categories_only_in_b.slice(0, 3).join(', ')}</span></span> },
          ]}
        />
      </Card>
    </div>
  )
}

function PromptTemplates() {
  const t = useQuery(() => plans.promptTemplates())
  return (
    <Card title="Prompt templates" subtitle="The exact instructions sent to the AI. Each is a versioned file, so any plan can be traced to the wording that produced it.">
      <Table
        rows={t.data}
        columns={[
          { key: 'name', label: 'Template', render: (r) => <><div className="strong">{humanize(r.name)}</div><div className="small muted">{r.purpose}</div></> },
          { key: 'version', label: 'Version', render: (r) => <Badge value={r.version} tone="neutral" plain /> },
          { key: 'file_path', label: 'File', render: (r) => <span className="source">{r.file_path}</span> },
          { key: 'content_hash', label: 'Fingerprint', render: (r) => <span className="source">{r.content_hash.slice(0, 12)}</span> },
        ]}
      />
    </Card>
  )
}
