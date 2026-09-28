import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, FileText, RefreshCw, Search, ShieldAlert, Upload, X, XCircle } from 'lucide-react'
import type { Json } from '../api/client'
import { documents } from '../api/endpoints'
import { DOCUMENT_TYPES, DepartmentSelect } from '../components/pickers'
import { Alert, Badge, Button, Card, Empty, Field, KeyValue, Modal, PageHeader, Table, Tabs, fmtDate, fmtDay, humanize } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

export function DocumentsPage() {
  const { can } = useAuth()
  const [filters, setFilters] = useState({ status_filter: '', document_type: '' })
  const [text, setText] = useState('')
  const [upload, setUpload] = useState(false)
  const [open, setOpen] = useState<Json | null>(null)
  const [tab, setTab] = useState('all')
  const list = useQuery(() => documents.list(filters), [JSON.stringify(filters)])
  const suspicious = useQuery(() => documents.suspicious())
  const q = text.trim().toLowerCase()
  const rows = (list.data ?? []).filter((d: Json) => !q || `${d.document_code} ${d.title}`.toLowerCase().includes(q))
  return (
    <div className="stack">
      <PageHeader
        title="Documents"
        subtitle="The company policies, handbooks and procedures that every plan is written from. Each upload is checked, split into sections and scanned for unsafe text."
        actions={can(...GENERATORS) && <Button variant="primary" icon={Upload} onClick={() => setUpload(true)}>Upload document</Button>}
      />
      <Tabs active={tab} onChange={setTab} tabs={[{ id: 'all', label: 'All documents', icon: FileText, count: list.data?.length }, { id: 'suspicious', label: 'Flagged text', icon: ShieldAlert, count: suspicious.data?.length }]} />
      {tab === 'all' && (
        <Card
          title={`${rows.length} document${rows.length === 1 ? '' : 's'}`}
          actions={
            <>
              <div className="search-input" style={{ width: 220 }}>
                <Search size={15} />
                <input className="input" placeholder="Search code or title" value={text} onChange={(e) => setText(e.target.value)} />
              </div>
              <select className="input" style={{ width: 150 }} value={filters.status_filter} onChange={(e) => setFilters({ ...filters, status_filter: e.target.value })} aria-label="Status">
                <option value="">Any status</option>
                {['ACTIVE', 'OBSOLETE', 'EXPIRED', 'QUARANTINED'].map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
              </select>
              <select className="input" style={{ width: 200 }} value={filters.document_type} onChange={(e) => setFilters({ ...filters, document_type: e.target.value })} aria-label="Type">
                <option value="">Any type</option>
                {DOCUMENT_TYPES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
              </select>
            </>
          }
        >
          <Table
            rows={rows}
            empty={list.loading ? 'Loading…' : 'No documents match.'}
            onRowClick={setOpen}
            columns={[
              { key: 'title', label: 'Document', render: (d) => <><div className="strong">{d.title}</div><div className="source">{d.document_code} · v{d.version}</div></> },
              { key: 'document_type', label: 'Type', render: (d) => <span className="small muted">{humanize(d.document_type)}</span> },
              { key: 'status', label: 'Status', render: (d) => <Badge value={d.status} /> },
              { key: 'precedence_rank', label: 'Priority', render: (d) => <span className="small" title="Lower number wins when two documents disagree">{d.precedence_rank}</span> },
              { key: 'effective_date', label: 'In effect from', render: (d) => <span className="small nowrap">{fmtDay(d.effective_date)}</span> },
              { key: 'file_extension', label: 'File', render: (d) => <span className="source">{d.file_extension}</span> },
            ]}
          />
        </Card>
      )}
      {tab === 'suspicious' && <SuspiciousChunks rows={suspicious.data} />}
      {upload && <UploadModal onClose={() => setUpload(false)} onDone={list.reload} />}
      {open && <DocumentModal doc={open} onClose={() => setOpen(null)} onChange={list.reload} />}
    </div>
  )
}

function UploadModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [form, setForm] = useState({ document_code: '', title: '', document_type: 'HR_POLICY', version: '1', effective_date: new Date().toISOString().slice(0, 10), expiry_date: '', department_id: '', notes: '' })
  const [autoParse, setAutoParse] = useState(true)
  const up = useAction(async () => {
    const fd = new FormData()
    fd.append('file', file as File)
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
    const res = await documents.upload(fd)
    if (autoParse) {
      // The file is already stored at this point; a failed read shouldn't look like a failed upload.
      try {
        res.parse = await documents.parse(res.document.id)
      } catch (e) {
        res.parseError = e instanceof Error ? e.message : String(e)
      }
    }
    return res
  }, 'Document uploaded')
  const checks: Json[] = up.result?.validation ?? up.error?.details?.checks ?? []
  const set = (k: string, v: string) => setForm({ ...form, [k]: v })
  return (
    <Modal
      open
      wide
      title="Upload a document"
      onClose={onClose}
      footer={
        up.result ? <Button variant="primary" onClick={() => { onDone(); onClose() }}>Done</Button> : (
          <>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="primary" icon={Upload} loading={up.running} disabled={!file || !form.document_code || !form.title} onClick={() => up.run()}>Upload and check</Button>
          </>
        )
      }
    >
      <div className="stack">
        <label className="card" style={{ display: 'block', cursor: 'pointer', borderStyle: 'dashed', boxShadow: 'none', background: 'var(--surface-2)' }}>
          <div className="empty" style={{ padding: 24 }}>
            <div className="empty-icon"><Upload size={20} /></div>
            <div className="empty-title">{file ? file.name : 'Choose a PDF or Word file'}</div>
            <div className="small">{file ? `${Math.round(file.size / 1024)} KB · click to change` : 'Up to 25 MB'}</div>
          </div>
          <input type="file" accept=".pdf,.docx" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <div className="form-grid">
          <Field label="Document code" hint="Reuse an existing code with a higher version to replace it"><input className="input" value={form.document_code} onChange={(e) => set('document_code', e.target.value)} placeholder="POL-INFOSEC-001" /></Field>
          <Field label="Title"><input className="input" value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="Information Security Policy" /></Field>
          <Field label="Type"><select className="input" value={form.document_type} onChange={(e) => set('document_type', e.target.value)}>{DOCUMENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select></Field>
          <Field label="Version"><input className="input" type="number" min={1} value={form.version} onChange={(e) => set('version', e.target.value)} /></Field>
          <Field label="In effect from"><input className="input" type="date" value={form.effective_date} onChange={(e) => set('effective_date', e.target.value)} /></Field>
          <Field label="Expires (optional)"><input className="input" type="date" value={form.expiry_date} onChange={(e) => set('expiry_date', e.target.value)} /></Field>
          <Field label="Department"><DepartmentSelect value={form.department_id} onChange={(v) => set('department_id', v)} allowEmpty="Whole company" /></Field>
          <Field label="Notes (optional)"><input className="input" value={form.notes} onChange={(e) => set('notes', e.target.value)} /></Field>
        </div>
        <label className="check"><input type="checkbox" checked={autoParse} onChange={(e) => setAutoParse(e.target.checked)} /> Read and index the document straight after upload</label>
        {checks.length > 0 && (
          <div>
            <div className="section-label">Upload checks</div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 8 }}>
              {checks.map((c) => (
                <div key={c.check} className="row gap-sm small" style={{ alignItems: 'flex-start' }}>
                  {c.passed ? <CheckCircle2 size={16} className="good" /> : <XCircle size={16} className="bad" />}
                  <div><div className="strong">{humanize(c.check)}</div><div className="subtle">{c.message}</div></div>
                </div>
              ))}
            </div>
          </div>
        )}
        {up.result && <Alert kind="success">{up.result.message}{up.result.parse ? ` ${up.result.parse.message}` : ''}</Alert>}
        {up.result?.parseError && <Alert kind="warn">The document was saved, but reading it failed: {up.result.parseError}. Open it from the list and choose "Re-read document" to try again.</Alert>}
        {up.result?.superseded_document_id && <Alert kind="info">The previous version is now obsolete. <Link to={`/policy-updates?doc=${up.result.document.id}`}>See which plans are affected</Link>.</Alert>}
      </div>
    </Modal>
  )
}

function DocumentModal({ doc, onClose, onChange }: { doc: Json; onClose: () => void; onChange: () => void }) {
  const { can } = useAuth()
  const [section, setSection] = useState('')
  const versions = useQuery(() => documents.versions(doc.id), [doc.id])
  const chunks = useQuery(() => documents.chunks(doc.id), [doc.id])
  const parse = useAction(() => documents.parse(doc.id, true), (r: Json) => r.message)
  const [trace, setTrace] = useState<Json | null>(null)
  const shown = (chunks.data ?? []).filter((c: Json) => !section || c.section_id === section)
  return (
    <Modal open wide title={doc.title} onClose={onClose}>
      <div className="stack">
        <div className="row wrap gap-sm">
          <Badge value={doc.status} /> <span className="source">{doc.document_code} · v{doc.version}</span>
          <span className="grow" />
          {can(...GENERATORS) && <Button size="sm" icon={RefreshCw} loading={parse.running} onClick={async () => { await parse.run(); chunks.reload(); onChange() }}>Re-read document</Button>}
          {doc.version > 1 && can(...GENERATORS) && <Link className="btn btn-sm btn-secondary" to={`/policy-updates?doc=${doc.id}`}>See what changed <ArrowRight size={14} /></Link>}
        </div>
        <div className="grid grid-2">
          <KeyValue items={[['Type', humanize(doc.document_type)], ['Priority rank', doc.precedence_rank], ['In effect from', fmtDay(doc.effective_date)], ['Expires', fmtDay(doc.expiry_date)], ['Uploaded', fmtDate(doc.created_at)]]} />
          <KeyValue items={[['File', `${doc.file_name} (${Math.round(doc.file_size_bytes / 1024)} KB)`], ['Fingerprint', <span className="source">{doc.content_hash.slice(0, 20)}…</span>], ['Versions', versions.data?.map((v: Json) => `v${v.version} ${humanize(v.status).toLowerCase()}`).join(' · ')]]} />
        </div>
        <div className="row between wrap gap-sm">
          <h3>{chunks.data?.length ?? 0} sections of text</h3>
          <div className="search-input" style={{ width: 200 }}><Search size={15} /><input className="input" placeholder="Section, e.g. 2.3" value={section} onChange={(e) => setSection(e.target.value)} /></div>
        </div>
        {trace && (
          <div id="chunk-trace" style={{ scrollMarginTop: 8 }}><Card title={`Where ${trace.chunk_code} comes from`} actions={<button className="icon-btn" aria-label="Close" onClick={() => setTrace(null)}><X size={16} /></button>}>
            <div className="stack-sm">
              <KeyValue items={[['Document', `${trace.source.document_code} v${trace.source.version} (${humanize(trace.source.status).toLowerCase()})`], ['Location', `§${trace.location.section_id ?? '—'} ${trace.location.heading_path ?? ''} · page ${trace.location.page_number ?? '—'}`], ['Flagged for', trace.suspicion_reasons?.map((s: Json) => humanize(s.pattern)).join(', ') || 'Nothing']]} />
              <p className="quote small" style={{ margin: 0 }}>{trace.content}</p>
            </div>
          </Card></div>
        )}
        <Table
          rows={shown}
          onRowClick={async (c) => {
            setTrace(await documents.trace(c.chunk_code))
            requestAnimationFrame(() => document.getElementById('chunk-trace')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
          }}
          columns={[
            { key: 'section_id', label: 'Section', render: (c) => <><div className="strong small">§{c.section_id ?? '—'}</div><div className="source">p.{c.page_number ?? '—'}</div></> },
            { key: 'content', label: 'Text', render: (c) => <span className="small clamp">{c.content}</span> },
            { key: 'is_suspicious', label: '', render: (c) => c.is_suspicious && <Badge value="Flagged" tone="bad" /> },
          ]}
        />
      </div>
    </Modal>
  )
}

function SuspiciousChunks({ rows }: { rows?: Json[] }) {
  return (
    <Card title="Flagged text" subtitle="Passages that look like instructions aimed at the AI. They are stored but never sent to it.">
      {rows && !rows.length ? (
        <Empty icon={CheckCircle2} title="Nothing flagged">No unsafe text was found in any document.</Empty>
      ) : (
        <Table
          rows={rows}
          columns={[
            { key: 'content', label: 'Text', render: (c) => <><div className="small">{c.content}</div><div className="source" style={{ marginTop: 4 }}>{c.chunk_code}</div></> },
            { key: 'reasons', label: 'Why it was flagged', render: (c) => <div className="row wrap gap-xs">{c.suspicion_reasons.map((r: Json) => <Badge key={r.pattern} value={humanize(r.pattern)} tone="bad" />)}</div> },
          ]}
        />
      )}
    </Card>
  )
}
