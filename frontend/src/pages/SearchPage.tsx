import { useState, type FormEvent } from 'react'
import { Database, SearchX, Search as SearchIcon, SlidersHorizontal } from 'lucide-react'
import type { Json } from '../api/client'
import { search } from '../api/endpoints'
import { Alert, Badge, Button, Card, Empty, Field, Meter, PageHeader, humanize } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

const EXAMPLES = ['How long do I have to complete the security training?', 'Who approves annual leave?', 'What should I do if I lose my laptop?']

export function SearchPage() {
  const { can } = useAuth()
  const [q, setQ] = useState('')
  const [minSim, setMinSim] = useState(0.45)
  const [limit, setLimit] = useState(10)
  const [activeOnly, setActiveOnly] = useState(true)
  const [showOptions, setShowOptions] = useState(false)
  const coverage = useQuery(() => search.coverage())
  const run = useAction((query?: string) => search.semantic({ q: query ?? q, limit, min_similarity: minSim, active_only: activeOnly }))
  const embed = useAction(() => search.embedAll(false), (r: Json) => `Indexed ${r.chunks_embedded} sections; ${r.pending} still waiting`)
  const r = run.result as Json
  const submit = (e: FormEvent) => { e.preventDefault(); run.run() }
  const c = coverage.data
  return (
    <div className="stack">
      <PageHeader title="Search documents" subtitle="Ask a question in plain words. Results are matched by meaning, not exact keywords, across every company document." />
      <Card>
        <form className="stack-sm" onSubmit={submit}>
          <div className="row gap-sm">
            <div className="search-input grow">
              <SearchIcon size={16} />
              <input className="input" style={{ height: 44, fontSize: 15 }} autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Who approves annual leave?" aria-label="Question" />
            </div>
            <Button variant="primary" size="lg" type="submit" loading={run.running} disabled={q.trim().length < 2}>Search</Button>
            <Button size="lg" variant="ghost" icon={SlidersHorizontal} onClick={() => setShowOptions(!showOptions)} aria-expanded={showOptions} title="Search options" aria-label="Search options" />
          </div>
          {!r && (
            <div className="row wrap gap-xs">
              <span className="small subtle">Try:</span>
              {EXAMPLES.map((e) => <button type="button" key={e} className="chip" style={{ cursor: 'pointer' }} onClick={() => { setQ(e); run.run(e) }}>{e}</button>)}
            </div>
          )}
          {showOptions && (
            <div className="form-grid" style={{ paddingTop: 8 }}>
              <Field label={`How close a match: ${Math.round(minSim * 100)}%`} hint="Higher shows fewer, closer results"><input type="range" min={0} max={1} step={0.05} value={minSim} onChange={(e) => setMinSim(Number(e.target.value))} /></Field>
              <Field label="Number of results"><input className="input" type="number" min={1} max={50} value={limit} onChange={(e) => setLimit(Number(e.target.value))} /></Field>
              <Field label="Include"><label className="check" style={{ height: 36 }}><input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} /> Current documents only</label></Field>
            </div>
          )}
        </form>
      </Card>

      {r && (
        <div className="stack-sm">
          <div className="row between wrap gap-sm">
            <h3>{r.count ? `${r.count} matching passage${r.count === 1 ? '' : 's'}` : 'No matches'}</h3>
            {r.count > 0 && <Badge value={r.grounded ? 'Answer found in documents' : 'Weak matches only'} tone={r.grounded ? 'good' : 'warn'} />}
          </div>
          {!r.grounded && r.count > 0 && <Alert kind="warn">No document covers this topic closely. A plan would list it as a gap rather than make something up.</Alert>}
          {!r.count && <Card><Empty icon={SearchX} title="No document covers this">That's a useful answer: a plan asked about this topic would record it as a gap instead of inventing content.</Empty></Card>}
          {r.results.map((x: Json) => (
            <Card key={x.chunk_id}>
              <div className="stack-sm">
                <div className="row between gap-sm wrap">
                  <div className="row gap-sm wrap">
                    <span className="strong">{x.document.document_code}</span>
                    <span className="source">v{x.document.version} · §{x.location.section_id ?? '—'}</span>
                    <Badge value={x.document.status} />
                    {x.is_suspicious && <Badge value="Flagged text" tone="bad" />}
                  </div>
                  <div className="row gap-sm" style={{ width: 170 }} title="How closely this passage matches your question">
                    <Meter value={x.similarity * 100} tone="accent" />
                    <span className="small strong nowrap">{Math.round(x.similarity * 100)}%</span>
                  </div>
                </div>
                <p style={{ margin: 0 }}>{x.content}</p>
                <div className="small subtle">{humanize(x.document.document_type)} · priority rank {x.document.precedence_rank}</div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {c && (
        <div className="row gap-sm wrap small subtle">
          <Database size={14} /> {c.embedded} of {c.total_chunks} sections indexed
          {c.pending > 0 && <>· <span className="warn">{c.pending} waiting</span></>}
          {can(...GENERATORS) && c.pending > 0 && <Button size="sm" variant="ghost" loading={embed.running} onClick={async () => { await embed.run(); coverage.reload() }}>Index now</Button>}
        </div>
      )}
    </div>
  )
}
