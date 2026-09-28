import { useState } from 'react'
import { CheckCircle2, FileCode2, KeyRound, Link2, Server, RefreshCw, ShieldCheck, SlidersHorizontal, XCircle, Zap } from 'lucide-react'
import type { Json } from '../api/client'
import { config, genai, plans } from '../api/endpoints'
import { Alert, Badge, Button, Card, CardLink, KeyValue, PageHeader, Spinner, Table, humanize } from '../components/ui'
import { GENERATORS, useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

export function AIPage() {
  const { can } = useAuth()
  const status = useQuery(() => genai.status())
  const templates = useQuery(() => plans.promptTemplates())
  const generation = useQuery(() => config.get('generation'))
  const [tests, setTests] = useState<Record<string, Json>>({})
  const test = useAction(async (provider: string) => {
    const r = await genai.test(provider)
    setTests((t) => ({ ...t, [provider]: r }))
    return r
  })
  if (!status.data) return <Spinner />
  const s = status.data
  const g = generation.data?.value
  return (
    <div className="stack">
      <PageHeader title="AI settings" subtitle="The AI services that write plans, tried in order. If one fails or runs out of tries, the next takes over automatically." actions={<Button icon={RefreshCw} onClick={status.reload}>Refresh</Button>} />
      <Alert kind="info">
        <strong>Keys stay on the server.</strong> API keys are set in the server's <code>.env</code> file (GENAI_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY) and are never sent to your browser. The local model (Ollama) needs no key. GENAI_PROVIDER and GENAI_FALLBACK_PROVIDERS set the order.
      </Alert>
      <Card title="Services, in order" icon={Link2} subtitle="Use Test to send a tiny request and confirm a service works.">
        {s.chain.map((p: Json, i: number) => {
          const t = tests[p.provider]
          return (
            <div className="provider" key={p.provider}>
              <span className="step-no">{i + 1}</span>
              <div>
                <div className="row wrap gap-sm">
                  <strong>{humanize(p.provider)}</strong>
                  <Badge value={p.role === 'primary' ? 'First choice' : 'Backup'} tone={p.role === 'primary' ? 'info' : 'neutral'} plain />
                  <Badge value={p.usable ? 'Ready' : p.local && p.provider !== 'offline' ? 'Not running' : 'Not set up'} tone={p.usable ? 'good' : p.local ? 'warn' : 'muted'} />
                  {p.local ? <Badge value="Runs on this machine" tone="neutral" plain /> : p.free_tier && <Badge value="Free tier" tone="neutral" plain />}
                  <span className="source">{p.model}</span>
                </div>
                <div className="small muted" style={{ marginTop: 4 }}>
                  {p.local ? <Server size={13} style={{ verticalAlign: '-2px' }} /> : <KeyRound size={13} style={{ verticalAlign: '-2px' }} />}{' '}
                  {p.skip_reason ?? (p.key_configured === null ? 'No key needed' : 'Key is set on the server')}
                  {p.max_request_tokens && ` · handles prompts up to about ${Number(p.max_request_tokens).toLocaleString()} tokens (${p.limit_note ?? 'free-tier limit'}), so bigger requests go straight to the next service`}
                </div>
                {t && (
                  <div className={`test-result ${t.ok ? 'good' : 'bad'}`}>
                    {t.ok ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
                    <span>{t.ok ? 'Working. ' : 'Not working. '}<span className="muted">{t.message}{t.kind ? ` (${humanize(t.kind).toLowerCase()})` : ''} · {t.duration_ms} ms</span></span>
                  </div>
                )}
              </div>
              {can(...GENERATORS) && (
                <Button size="sm" icon={Zap} disabled={test.running} onClick={() => test.run(p.provider)}>Test</Button>
              )}
            </div>
          )
        })}
      </Card>
      <div className="grid grid-2">
        <Card title="Writing settings" icon={SlidersHorizontal} actions={<CardLink to="/config">Edit</CardLink>}>
          {g ? (
            <KeyValue
              items={[
                ['Tries per service', `${g.retry?.max_attempts} (never more than 3)`],
                ['Wait between tries', `${g.retry?.backoff_seconds} s, doubling up to ${g.retry?.backoff_cap_seconds} s`],
                ['Minimum match score', `${Math.round((g.retrieval?.min_similarity ?? 0) * 100)}%. Weaker matches count as a gap`],
                ['Passages per requirement', g.retrieval?.per_requirement],
                ['Longest reply allowed', `${g.parameters?.max_tokens} tokens`],
                ['Effort, temperature, seed', `${g.parameters?.effort}, ${g.parameters?.temperature}, ${g.parameters?.seed}`],
                ['Default backups', (g.fallback_chain ?? []).map(humanize).join(', then ')],
              ]}
            />
          ) : <Spinner />}
        </Card>
        <Card title="How the AI is kept honest" icon={ShieldCheck}>
          <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
            <li>The exact instructions and reply for every plan are saved, so any plan can be traced.</li>
            <li>Document text is marked as untrusted, and flagged passages are never sent.</li>
            <li>If no document supports a topic, it is listed as a gap instead of being made up.</li>
            <li>Replies must follow a fixed format. A bad reply is retried at most 3 times per service.</li>
            <li>Every plan is then checked by fixed rules, with no AI, against the requirement list.</li>
          </ul>
        </Card>
      </div>
      <Card title="Prompt templates" icon={FileCode2}>
        <Table rows={templates.data} columns={[{ key: 'name', label: 'Template', render: (r) => <><div className="strong">{humanize(r.name)}</div><div className="small muted">{r.purpose}</div></> }, { key: 'version', label: 'Version', render: (r) => <Badge value={r.version} tone="neutral" plain /> }, { key: 'content_hash', label: 'Fingerprint', render: (r) => <span className="source">{r.content_hash.slice(0, 12)}</span> }]} />
      </Card>
    </div>
  )
}
