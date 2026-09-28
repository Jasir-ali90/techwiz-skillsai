import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { BookOpen, CalendarClock, Check, CheckSquare, ClipboardCheck, Clock, Cpu, Download, FileWarning, GitCompare, GraduationCap, History, Layers, ListTodo, Play, RefreshCw, Repeat, ShieldCheck } from 'lucide-react'
import type { Json } from '../api/client'
import { plans, progress, review, validation } from '../api/endpoints'
import { DecisionModal } from '../components/DecisionModal'
import { Alert, Badge, Button, Card, CardLink, Empty, ErrorBox, KeyValue, PageHeader, Spinner, Stat, Table, Tabs, fmtDate, humanize, pct } from '../components/ui'
import { Attempts } from './PlansPage'
import { GENERATORS, REVIEWERS, STAFF, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'
import { AuditTable } from './AuditPage'

export function PlanDetailPage() {
  const { id = '' } = useParams()
  const [tab, setTab] = useState('modules')
  const plan = useQuery(() => plans.get(id), [id])
  if (plan.loading && !plan.data) return <Spinner />
  if (plan.error) return <ErrorBox error={plan.error} onRetry={plan.reload} />
  const p = plan.data
  return (
    <div>
      <PageHeader
        back={{ to: '/plans', label: 'All plans' }}
        title={p.title}
        subtitle={
          <span className="row wrap gap-sm" style={{ marginTop: 4 }}>
            <Badge value={p.verification_status ?? 'NOT_CHECKED'} />
            <Badge value={p.is_current ? 'Current version' : p.status} tone={p.is_current ? 'info' : undefined} />
            <span className="small muted">Written by {humanize(p.provider)} on {fmtDate(p.generated_at)}</span>
          </span>
        }
      />
      <div className="grid grid-stats" style={{ marginBottom: 24 }}>
        <Stat icon={Layers} label="Modules" value={p.counts.modules} />
        <Stat icon={ListTodo} label="Tasks" value={p.counts.tasks} />
        <Stat icon={CheckSquare} label="Checklist items" value={p.counts.checklist_items} />
        <Stat icon={BookOpen} label="Quiz questions" value={p.counts.quiz_questions} />
        <Stat icon={GraduationCap} label="Assessments" value={p.counts.assessments} />
        <Stat icon={FileWarning} label="Topics not covered" value={p.gaps.length} hint={p.gaps.length ? 'No source document' : 'Everything is sourced'} tone={p.gaps.length ? 'warn' : 'good'} />
      </div>
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'modules', label: 'Plan content', icon: Layers },
          { id: 'validation', label: 'Quality check', icon: ShieldCheck },
          { id: 'comparison', label: 'AI vs rules', icon: GitCompare },
          { id: 'run', label: 'How it was written', icon: Cpu },
          { id: 'consistency', label: 'Consistency', icon: Repeat },
          { id: 'outdated', label: 'Outdated sources', icon: CalendarClock },
          { id: 'audit', label: 'History', icon: History },
        ]}
      />
      {tab === 'modules' && <Modules plan={p} onChange={plan.reload} />}
      {tab === 'validation' && <ValidationTab planId={id} onChange={plan.reload} />}
      {tab === 'comparison' && <ComparisonTab planId={id} />}
      {tab === 'run' && <RunTab planId={id} />}
      {tab === 'consistency' && <ConsistencyTab planId={id} />}
      {tab === 'outdated' && <OutdatedTab planId={id} />}
      {tab === 'audit' && <AuditTable entityType="plan" entityId={id} />}
    </div>
  )
}

export function SourceRef({ item }: { item: Json }) {
  return (
    <span className="source" title={`Requirement ${item.requirement_code}, from ${item.source_document_code} version ${item.source_document_version}, section ${item.source_section_id}`}>
      {item.source_document_code ?? '?'} v{item.source_document_version ?? '?'} §{item.source_section_id ?? '—'} · {item.requirement_code}
      {item.source_document_status && item.source_document_status !== 'ACTIVE' && <> <Badge value={item.source_document_status} /></>}
    </span>
  )
}

function Modules({ plan, onChange }: { plan: Json; onChange: () => void }) {
  const { can } = useAuth()
  const [score, setScore] = useState<Record<string, string>>({})
  const set = useAction((type: string, itemId: string, status: string) => progress.setItem(type, itemId, status), 'Progress saved')
  const assess = useAction((aid: string, s: number) => progress.assessment(aid, { score: s }), (r: Json) => (r.passed ? 'Assessment passed' : 'Result saved: not passed yet'))
  const toggle = async (type: string, item: Json) => {
    await set.run(type, item.id, item.completion_status === 'COMPLETED' ? 'NOT_STARTED' : 'COMPLETED')
    onChange()
  }
  return (
    <div className="stack-sm">
      {plan.gaps.length > 0 && (
        <Alert kind="warn">
          <strong>Not covered: {plan.gaps.map((g: Json) => g.topic).join(', ')}.</strong> No active company document supports {plan.gaps.length > 1 ? 'these topics' : 'this topic'}, so nothing was written for {plan.gaps.length > 1 ? 'them' : 'it'}.
        </Alert>
      )}
      {plan.modules.map((m: Json) => (
        <details key={m.id} className="module">
          <summary>
            <div className="grow">
              <div className="strong">{m.title}</div>
              <div className="small subtle row gap-sm wrap" style={{ marginTop: 2 }}>
                <span className="row gap-xs"><Clock size={13} /> {m.estimated_duration_minutes} min</span>
                <span>· {m.requirement_codes.length} requirement{m.requirement_codes.length === 1 ? '' : 's'}</span>
                <span>· {m.tasks.length} tasks</span>
              </div>
            </div>
            <div className="row gap-sm wrap">
              {m.is_outdated && <Badge value="Outdated" tone="bad" />}
              {m.regeneration_count > 0 && <Badge value={`Rewritten ${m.regeneration_count}×`} tone="neutral" />}
              <Badge value={humanize(m.due_stage)} tone="info" plain />
              <Badge value={m.completion_status} />
            </div>
          </summary>
          <div className="module-body stack">
            <div className="row between gap wrap">
              <p className="grow" style={{ margin: 0 }}>{m.purpose}</p>
              {can(...STAFF) && (
                <Button size="sm" icon={ClipboardCheck} onClick={() => toggle('module', m)}>
                  {m.completion_status === 'COMPLETED' ? 'Mark as not started' : 'Mark module complete'}
                </Button>
              )}
            </div>
            <div className="small">Source: <SourceRef item={m} /></div>
            <div className="grid grid-2">
              <div>
                <div className="section-label">What they will learn</div>
                <ul>{m.learning_objectives.map((o: string, i: number) => <li key={i}>{o}</li>)}</ul>
              </div>
              <div>
                <div className="section-label">How</div>
                <ul>{m.learning_activities.map((o: string, i: number) => <li key={i}>{o}</li>)}</ul>
              </div>
            </div>
            <ItemList title="Tasks" items={m.tasks} text={(t) => t.description} extra={(t) => <Badge value={t.difficulty} tone="neutral" plain />} onToggle={can(...STAFF) ? (t) => toggle('task', t) : undefined} />
            <ItemList title="Checklist" items={m.checklist} text={(c) => c.activity} extra={(c) => <span className="small subtle">{c.is_required ? 'Required' : 'Optional'} · {c.responsible_person}</span>} onToggle={can(...STAFF) ? (c) => toggle('checklist_item', c) : undefined} />
            {m.quiz.length > 0 && (
              <div>
                <div className="section-label">Quiz</div>
                {m.quiz.map((q: Json, qi: number) => (
                  <div className="item" key={q.id}>
                    <div className="row gap-sm wrap"><span className="strong">{qi + 1}. {q.question}</span> {q.is_outdated && <Badge value="Outdated" tone="bad" />}</div>
                    <div className="row wrap gap-xs" style={{ margin: '8px 0 6px' }}>
                      {q.options.map((o: string) => {
                        const right = q.correct_answer.includes(o)
                        return (
                          <span key={o} className="chip" style={right ? { background: 'var(--good-soft)', color: 'var(--good)', borderColor: 'transparent', fontWeight: 600 } : undefined}>
                            {right && <Check size={13} aria-label="correct answer" />} {o}
                          </span>
                        )
                      })}
                    </div>
                    <div className="small subtle">{humanize(q.question_type)} · <SourceRef item={q} /></div>
                  </div>
                ))}
              </div>
            )}
            {m.scenarios.length > 0 && (
              <div>
                <div className="section-label">Scenarios</div>
                {m.scenarios.map((s: Json, i: number) => (
                  <div className="item" key={i}>
                    <div className="strong">{s.title}</div>
                    <div className="small">{s.situation}</div>
                    <div className="small good" style={{ marginTop: 4 }}>What to do: {s.expected_action}</div>
                  </div>
                ))}
              </div>
            )}
            {m.assessments.map((a: Json) => (
              <div key={a.id} className="card" style={{ boxShadow: 'none', background: 'var(--surface-2)' }}>
                <div className="card-body stack-sm">
                  <div className="row wrap gap-sm between">
                    <div className="row gap-sm"><GraduationCap size={17} className="muted" /><span className="strong">{a.title}</span></div>
                    <div className="row gap-sm"><span className="small muted">Pass mark {a.passing_score}% · due {humanize(a.due_stage).toLowerCase()}</span><Badge value={a.completion_status} /></div>
                  </div>
                  <ul className="small">{a.rubric.map((r: Json) => <li key={r.id}><strong>{r.criterion}</strong> ({r.weight}%): {r.pass_condition}</li>)}</ul>
                  {can(...STAFF) && (
                    <div className="row gap-sm">
                      <input className="input" style={{ width: 120 }} type="number" min={0} max={100} placeholder="Score %" aria-label="Score" value={score[a.id] ?? ''} onChange={(e) => setScore({ ...score, [a.id]: e.target.value })} />
                      <Button disabled={score[a.id] === undefined || score[a.id] === ''} loading={assess.running} onClick={async () => { await assess.run(a.id, Number(score[a.id])); onChange() }}>
                        Save result
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </details>
      ))}
    </div>
  )
}

function ItemList({ title, items, text, extra, onToggle }: { title: string; items: Json[]; text: (i: Json) => string; extra?: (i: Json) => ReactNode; onToggle?: (i: Json) => void }) {
  if (!items.length) return null
  return (
    <div>
      <div className="section-label">{title}</div>
      {items.map((i) => {
        const done = i.completion_status === 'COMPLETED'
        return (
          <div className="item row gap" key={i.id} style={{ alignItems: 'flex-start' }}>
            {onToggle && <input type="checkbox" style={{ marginTop: 3 }} checked={done} onChange={() => onToggle(i)} aria-label={`Mark "${text(i)}" done`} />}
            <div className="grow">
              <div style={done ? { textDecoration: 'line-through', color: 'var(--text-3)' } : undefined}>{text(i)}</div>
              <div className="row wrap gap-sm" style={{ marginTop: 4 }}>
                <Badge value={humanize(i.due_stage)} tone="info" plain /> {extra?.(i)} {i.is_outdated && <Badge value="Outdated" tone="bad" />}
                <SourceRef item={i} />
              </div>
            </div>
            {!onToggle && <Badge value={i.completion_status} />}
          </div>
        )
      })}
    </div>
  )
}

function ValidationTab({ planId, onChange }: { planId: string; onChange: () => void }) {
  const { can } = useAuth()
  const [filter, setFilter] = useState({ rule: '', severity: '' })
  const [decide, setDecide] = useState<Json | null>(null)
  const result = useQuery(() => validation.result(planId).catch(() => null), [planId])
  const run = useAction(() => validation.run(planId), (r: Json) => `Check finished: ${humanize(r.verification_status).toLowerCase()}`)
  const r = run.result ?? result.data
  const findings = (r?.findings ?? []).filter((f: Json) => (!filter.rule || f.rule === filter.rule) && (!filter.severity || f.severity === filter.severity))
  const doRun = async () => { await run.run(); result.reload(); onChange() }
  const m = r?.metrics
  return (
    <div className="stack">
      <Card
        title="Automatic quality check"
        subtitle="13 rule-based checks, no AI involved. They confirm the plan covers every mandatory requirement and cites a current source."
        actions={<Button variant="primary" icon={Play} loading={run.running} onClick={doRun}>{r ? 'Run again' : 'Run check'}</Button>}
      >
        {!r ? (
          <Empty icon={ShieldCheck} title="Not checked yet">Run the check to see how complete and well-sourced this plan is.</Empty>
        ) : (
          <div className="stack">
            <div className="row wrap gap-sm">
              <Badge value={r.verification_status} />
              <span className="small muted">Checked {fmtDate(r.run_at)} in {(r.duration_ms / 1000).toFixed(1)} s · rules v{r.rule_set_version}</span>
            </div>
            {r.status_reasons?.length > 0 && <ul className="small muted">{r.status_reasons.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>}
            <div className="grid grid-stats">
              <Stat label="Mandatory items covered" value={pct(m.mandatory_requirement_coverage_score)} tone={m.mandatory_requirement_coverage_score >= 100 ? 'good' : 'bad'} hint={m.mandatory_requirement_coverage_score >= 100 ? 'All included' : 'Some missing'} />
              <Stat label="Items with a source" value={pct(m.source_traceability_score)} tone={m.source_traceability_score >= 100 ? 'good' : 'bad'} />
              <Stat label="Consistent with matrix" value={pct(m.requirement_consistency_score)} />
              <Stat label="Missing items" value={m.missing_requirement_count} tone={m.missing_requirement_count ? 'bad' : 'good'} />
              <Stat label="Unsupported items" value={m.unsupported_requirement_count} tone={m.unsupported_requirement_count ? 'bad' : 'good'} />
              <Stat label="Contradictions" value={m.contradiction_count} hint={`${r.extra_metrics?.unresolved_contradictions ?? 0} unresolved`} tone={r.extra_metrics?.unresolved_contradictions ? 'warn' : undefined} />
            </div>
            <details>
              <summary className="link small" style={{ cursor: 'pointer' }}>Show results per rule</summary>
              <div style={{ marginTop: 10 }}>
                <Table
                  rows={Object.entries(r.rule_summaries).map(([rule, s]: [string, Json]) => ({ rule, ...s }))}
                  rowKey={(x) => x.rule}
                  columns={[
                    { key: 'rule', label: 'Rule', render: (x) => <strong>{humanize(x.rule)}</strong> },
                    { key: 'findings', label: 'Findings', render: (x) => (x.findings ? <Badge value={x.findings} tone="warn" plain /> : <Check size={16} className="good" />) },
                    { key: 'detail', label: 'Summary', render: (x) => <span className="small muted">{Object.entries(x).filter(([k]) => !['rule', 'findings', 'duration_ms'].includes(k)).slice(0, 4).map(([k, v]) => `${humanize(k)}: ${typeof v === 'object' ? JSON.stringify(v).slice(0, 40) : v}`).join(' · ')}</span> },
                    { key: 'duration_ms', label: 'Time', render: (x) => <span className="small subtle">{x.duration_ms} ms</span> },
                  ]}
                />
              </div>
            </details>
          </div>
        )}
      </Card>
      {r && (
        <Card
          title={findings.length ? `${findings.length} finding${findings.length === 1 ? '' : 's'}` : 'Findings'}
          subtitle="Anything the rules flagged. Open items can be approved, fixed or regenerated by a reviewer."
          actions={
            <>
              <select className="input" style={{ width: 200 }} value={filter.rule} onChange={(e) => setFilter({ ...filter, rule: e.target.value })}>
                <option value="">All rules</option>
                {Object.keys(r.rule_summaries).map((k) => <option key={k} value={k}>{humanize(k)}</option>)}
              </select>
              <select className="input" style={{ width: 160 }} value={filter.severity} onChange={(e) => setFilter({ ...filter, severity: e.target.value })}>
                <option value="">Any severity</option>
                {['CRITICAL', 'ERROR', 'WARNING', 'INFO'].map((k) => <option key={k} value={k}>{humanize(k)}</option>)}
              </select>
            </>
          }
        >
          <Table
            rows={findings}
            empty="Nothing was flagged. This plan passed every check."
            columns={[
              { key: 'severity', label: 'Severity', render: (f) => <Badge value={f.severity} /> },
              { key: 'message', label: 'What was found', render: (f) => <><div className="small">{f.message}</div><div className="small subtle">{humanize(f.rule)}{f.requirement_code ? ` · ${f.requirement_code}` : ''}</div></> },
              { key: 'item_status', label: 'Item', render: (f) => <Badge value={f.item_status} /> },
              { key: 'review_status', label: 'Review', render: (f) => <Badge value={f.review_status} /> },
              { key: 'act', label: '', render: (f) => can(...REVIEWERS) && f.review_status === 'OPEN' && <Button size="sm" onClick={() => setDecide(f)}>Review</Button> },
            ]}
          />
        </Card>
      )}
      <DecisionModal finding={decide} onClose={() => setDecide(null)} onDone={doRun} />
    </div>
  )
}

function ComparisonTab({ planId }: { planId: string }) {
  const [onlyMismatch, setOnlyMismatch] = useState(false)
  const existing = useQuery(() => review.comparison(planId).catch(() => null), [planId])
  const build = useAction(() => review.compare(planId), 'Comparison ready')
  const exp = useAction(() => review.exportComparison(planId), 'CSV downloaded')
  const c = build.result ?? existing.data
  const rows = (c?.rows ?? []).filter((r: Json) => !onlyMismatch || r.match === 'MISMATCH')
  return (
    <Card
      title="What the AI wrote vs what the rules expect"
      subtitle="Compares each requirement's facts (mandatory, priority, source, due date), never the wording."
      actions={
        <>
          {c && <label className="check small"><input type="checkbox" checked={onlyMismatch} onChange={(e) => setOnlyMismatch(e.target.checked)} /> Differences only</label>}
          <Button icon={RefreshCw} loading={build.running} onClick={() => build.run()}>{c ? 'Rebuild' : 'Build comparison'}</Button>
          <Button icon={Download} disabled={!c} loading={exp.running} onClick={() => exp.run()}>CSV</Button>
        </>
      }
    >
      {!c ? (
        <Empty icon={GitCompare} title="No comparison yet">Build one to see, requirement by requirement, whether the AI and the rules agree.</Empty>
      ) : (
        <div className="stack">
          <div className="grid grid-stats">
            <Stat label="Requirements compared" value={c.summary.rows} />
            <Stat label="Agreement" value={pct(c.summary.agreement_percent)} tone={c.summary.mismatches ? 'warn' : 'good'} />
            <Stat label="Differences" value={c.summary.mismatches} tone={c.summary.mismatches ? 'warn' : 'good'} />
          </div>
          <Table
            rows={rows}
            rowKey={(r) => r.requirement_code}
            empty="No differences."
            columns={[
              { key: 'requirement_code', label: 'Requirement', render: (r) => <><div className="strong">{r.required_competency}</div><div className="source">{r.requirement_code}</div></> },
              { key: 'mandatory_or_optional', label: 'Type', render: (r) => <Badge value={r.mandatory_or_optional} /> },
              { key: 'priority', label: 'Priority', render: (r) => <Badge value={r.priority} /> },
              { key: 'src', label: 'Source', render: (r) => <span className="source">{r.source_document_code} §{r.source_section_id}</span> },
              { key: 'due_stage', label: 'Due', render: (r) => humanize(r.due_stage) },
              { key: 'match', label: 'Result', render: (r) => <Badge value={r.match === 'MATCH' ? 'Agrees' : 'Differs'} tone={r.match === 'MATCH' ? 'good' : 'warn'} /> },
              { key: 'explanation', label: 'Why', render: (r) => <span className="small muted">{r.explanation}</span> },
            ]}
          />
        </div>
      )}
    </Card>
  )
}

function RunTab({ planId }: { planId: string }) {
  const q = useQuery(() => plans.generationRun(planId), [planId])
  if (q.loading) return <Spinner />
  const runs: Json[] = q.data?.runs ?? []
  if (!runs.length) return <Card><Empty icon={Cpu} title="No AI run recorded" /></Card>
  return (
    <div className="stack">
      {[...runs].reverse().map((r) => (
        <Card
          key={r.id}
          icon={Cpu}
          title={<span className="row gap-sm wrap">{humanize(r.purpose)} <Badge value={r.status} /> {r.parameters?.fell_back && <Badge value="Backup service used" tone="warn" />}</span>}
          subtitle={fmtDate(r.started_at)}
        >
          <div className="stack">
            <div className="grid grid-2">
              <KeyValue
                items={[
                  ['Written by', <><strong>{humanize(r.provider)}</strong> <span className="source">{r.model}</span></>],
                  ['Services tried', (r.parameters?.provider_chain ?? []).map(humanize).join(', then ')],
                  ['Skipped', (r.parameters?.providers_skipped ?? []).map((s: Json) => `${humanize(s.provider)} (${humanize(s.kind).toLowerCase()})`).join(', ') || 'None'],
                  ['Time and tries', `${(r.duration_ms / 1000).toFixed(1)} s · ${r.attempt_count} ${r.attempt_count === 1 ? 'try' : 'tries'}`],
                  ['Tokens', `${r.token_usage?.input_tokens ?? '—'} in · ${r.token_usage?.output_tokens ?? '—'} out`],
                ]}
              />
              <KeyValue
                items={[
                  ['Prompt', <>{r.prompt_template_version} <span className="source">{String(r.parameters?.prompt_hash ?? '').slice(0, 10)}</span></>],
                  ['Temperature / seed', `${r.parameters?.temperature ?? '—'} / ${r.parameters?.seed ?? '—'}`],
                  ['Minimum match score', r.parameters?.retrieval?.min_similarity],
                  ['Documents used', <span className="small">{(r.source_documents ?? []).map((d: Json) => `${d.document_code} v${d.version}`).join(', ')}</span>],
                  ['Error', r.error],
                ]}
              />
            </div>
            <div>
              <div className="section-label">Each try</div>
              <Attempts attempts={r.attempts} />
            </div>
            <details className="json"><summary className="link small" style={{ cursor: 'pointer' }}>Show the exact prompt sent (document text is marked as untrusted)</summary><pre>{r.raw_request}</pre></details>
            <details className="json"><summary className="link small" style={{ cursor: 'pointer' }}>Show the raw AI response</summary><pre>{(r.raw_response ?? '').slice(0, 20000)}</pre></details>
          </div>
        </Card>
      ))}
    </div>
  )
}

function ConsistencyTab({ planId }: { planId: string }) {
  const { can } = useAuth()
  const [count, setCount] = useState(3)
  const q = useQuery(() => review.consistency(planId), [planId])
  const start = useAction(() => review.startConsistency(planId, count), 'Consistency test started. It runs in the background.')
  const latest: Json = q.data?.[0]
  // The test runs in the background; refresh on our own until it finishes.
  const inProgress = latest && ['PENDING', 'RUNNING'].includes(latest.status)
  const { reload } = q
  useEffect(() => {
    if (!inProgress) return
    const timer = setInterval(reload, 3000)
    return () => clearInterval(timer)
  }, [inProgress, reload])
  return (
    <Card
      title="Consistency test"
      subtitle="Writes the plan several times with the same inputs and checks the results agree on requirements, sources and topics."
      actions={
        can(...GENERATORS, ...REVIEWERS) && (
          <>
            <select className="input" style={{ width: 110 }} aria-label="Number of runs" value={count} onChange={(e) => setCount(Number(e.target.value))}>{[2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} runs</option>)}</select>
            <Button variant="primary" icon={Play} loading={start.running || !!inProgress} onClick={async () => { await start.run(); setTimeout(q.reload, 800) }}>{inProgress ? 'Running…' : 'Start'}</Button>
            <Button icon={RefreshCw} onClick={q.reload}>Refresh</Button>
          </>
        )
      }
    >
      {!latest ? (
        <Empty icon={Repeat} title="Not tested yet">Start a test to measure how repeatable this plan is.</Empty>
      ) : (
        <div className="stack">
          <div className="row wrap gap-sm"><Badge value={latest.status} /> <span className="small muted">{fmtDate(latest.created_at)}</span></div>
          <div className="grid grid-stats">
            <Stat label="Consistency score" value={latest.consistency_score === null ? '—' : pct(latest.consistency_score)} tone={latest.consistency_score >= 90 ? 'good' : 'warn'} />
            {Object.entries(latest.per_dimension ?? {}).map(([k, v]) => <Stat key={k} label={humanize(k)} value={pct(v as number)} />)}
          </div>
          <Table rows={latest.major_differences} rowKey={(_, i) => String(i)} empty="The runs agreed. No major differences." columns={[{ key: 'type', label: 'Difference', render: (d) => <Badge value={d.type} tone="warn" /> }, { key: 'v', label: 'Item', render: (d) => d.requirement_code ?? d.value }, { key: 'present_in_runs', label: 'Seen in runs', render: (d) => d.present_in_runs.join(', ') }]} />
          <details><summary className="link small" style={{ cursor: 'pointer' }}>Test settings</summary><div style={{ marginTop: 10 }}><KeyValue items={Object.entries(latest.parameters ?? {}).filter(([k]) => k !== 'fixed_chunk_set').map(([k, v]) => [humanize(k), String(v)] as [string, string])} /></div></details>
          {latest.error && <Alert kind="error">{latest.error}</Alert>}
        </div>
      )}
    </Card>
  )
}

function OutdatedTab({ planId }: { planId: string }) {
  const q = useQuery(() => plans.outdated(planId), [planId])
  if (q.loading) return <Spinner />
  const n = q.data?.outdated_items ?? 0
  return (
    <Card
      title={n ? `${n} item${n === 1 ? '' : 's'} cite an outdated source` : 'All sources are current'}
      subtitle="Items whose source document was replaced, withdrawn or changed since the plan was written."
      actions={<CardLink to="/policy-updates">Policy updates</CardLink>}
    >
      {n > 0 && <div className="row wrap gap-sm" style={{ marginBottom: 12 }}>{Object.entries(q.data?.by_status ?? {}).map(([k, v]) => <Badge key={k} value={`${humanize(k)} · ${v}`} tone="warn" />)}</div>}
      <Table rows={q.data?.items} empty="Every item in this plan cites a current document." columns={[{ key: 'item_type', label: 'Item', render: (i) => humanize(i.item_type) }, { key: 'status', label: 'Why', render: (i) => <Badge value={i.status} /> }, { key: 'text', label: 'Text', render: (i) => <span className="small">{i.text}</span> }, { key: 'cited', label: 'Cites', render: (i) => <span className="source">{i.cited}</span> }]} />
    </Card>
  )
}
