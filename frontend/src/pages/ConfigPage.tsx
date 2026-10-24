import { useState, useEffect } from 'react'
import { Bell, CheckCircle2, ListOrdered, RotateCcw, Save, Scale, Send, Sliders, Webhook } from 'lucide-react'
import type { Json } from '../api/client'
import { config, documents, webhooks } from '../api/endpoints'
import { Alert, Badge, Button, Card, JsonEditor, KeyValue, PageHeader, Spinner, Table, Tabs, humanize } from '../components/ui'
import { useAuth } from '../lib/auth'
import { useAction, useQuery } from '../lib/hooks'

export function ConfigPage() {
  const [tab, setTab] = useState<'settings' | 'webhooks'>('settings')

  return (
    <div className="stack">
      <PageHeader
        title="Configuration & Integrations"
        subtitle="Fine-tune verification policies, document precedence hierarchy, and enterprise Slack/MS Teams notification webhooks."
      />
      <Tabs
        active={tab}
        onChange={(t) => setTab(t as 'settings' | 'webhooks')}
        tabs={[
          { id: 'settings', label: 'System Parameters', icon: Sliders },
          { id: 'webhooks', label: 'Webhooks & Notifications', icon: Bell },
        ]}
      />

      {tab === 'settings' && <SystemSettingsView />}
      {tab === 'webhooks' && <WebhooksView />}
    </div>
  )
}

function SystemSettingsView() {
  const keys = useQuery(() => config.keys())
  const [key, setKey] = useState('precedence')

  return (
    <div className="split">
      <Card title="Settings">
        <div className="list-nav">
          {keys.data?.map((k: Json) => (
            <button key={k.key} className={key === k.key ? 'active' : ''} onClick={() => setKey(k.key)}>
              {humanize(k.key)} {k.source === 'database' && <Badge value="Changed" tone="info" plain />}
            </button>
          ))}
        </div>
      </Card>
      <ConfigEditor key={key} configKey={key} onSaved={keys.reload} />
    </div>
  )
}

function ConfigEditor({ configKey, onSaved }: { configKey: string; onSaved: () => void }) {
  const { can } = useAuth()
  const q = useQuery(() => config.get(configKey), [configKey])
  const [draft, setDraft] = useState<Json>(null)
  const [valid, setValid] = useState(true)
  const [version, setVersion] = useState(0)
  const save = useAction(() => config.put(configKey, draft ?? q.data.value), (r: Json) => `Saved (version ${r.version})`)
  const reset = useAction(() => config.reset(configKey), 'Reset to the default')
  const reapply = useAction(() => config.reapplyPrecedence(), (r: Json) => (r.documents_updated ? `${r.documents_updated} document priorities updated` : 'No document priorities needed changing'))
  if (!q.data) return <Spinner />
  const done = () => { q.reload(); onSaved(); setDraft(null); setVersion((v) => v + 1) }
  return (
    <div className="stack">
      <Card
        title={humanize(configKey)}
        actions={
          can('ADMIN') && (
            <>
              {q.data.source === 'database' && <Button variant="danger" icon={RotateCcw} loading={reset.running} onClick={async () => { await reset.run(); done() }}>Reset to default</Button>}
              <Button variant="primary" icon={Save} disabled={!valid || draft === null} loading={save.running} onClick={async () => { if (await save.run()) done() }}>Save changes</Button>
            </>
          )
        }
      >
        <div className="stack">
          <KeyValue items={[['Currently using', q.data.source === 'database' ? <Badge value="Your changes" tone="info" /> : <Badge value="Default file" tone="muted" />], ['Version', q.data.version], ['About', q.data.description]]} />
          <JsonEditor initial={q.data.value} resetKey={`${configKey}:${version}:${q.data.version}`} rows={24} onChange={(v, ok) => { setValid(ok); if (ok) setDraft(v) }} />
          {!can('ADMIN') && <Alert kind="info">You can look, but only administrators can save changes.</Alert>}
        </div>
      </Card>
      {configKey === 'precedence' && can('ADMIN') && (
        <Card title="Apply the new priority order" icon={ListOrdered} subtitle="After changing priorities, update existing documents. Then run step 4 on the Requirements page." actions={<Button icon={ListOrdered} loading={reapply.running} onClick={() => reapply.run()}>Update documents</Button>}>
          {reapply.result && <Table rows={(reapply.result as Json).changes} rowKey={(c) => `${c.document_code}${c.version}`} empty="Every document already had the right priority." columns={[{ key: 'document_code', label: 'Document' }, { key: 'version', label: 'Version' }, { key: 'old_rank', label: 'Was' }, { key: 'new_rank', label: 'Now' }]} />}
          <ResolveConflict />
        </Card>
      )}
    </div>
  )
}

function ResolveConflict() {
  const docs = useQuery(() => documents.list({ status_filter: 'ACTIVE' }))
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const resolve = useAction(() => config.resolvePrecedence([a, b]))
  const r = resolve.result as Json
  const opts = docs.data?.map((d: Json) => <option key={d.id} value={d.id}>{d.document_code} v{d.version} (priority {d.precedence_rank})</option>)
  return (
    <div className="stack-sm" style={{ marginTop: 16 }}>
      <div className="row gap-sm"><Scale size={16} className="muted" /><strong>Which document wins a conflict?</strong></div>
      <div className="row wrap gap-sm">
        <select className="input" style={{ maxWidth: 280 }} value={a} onChange={(e) => setA(e.target.value)}><option value="">First document…</option>{opts}</select>
        <select className="input" style={{ maxWidth: 280 }} value={b} onChange={(e) => setB(e.target.value)}><option value="">Second document…</option>{opts}</select>
        <Button disabled={!a || !b || a === b} loading={resolve.running} onClick={() => resolve.run()}>Compare</Button>
      </div>
      {r && <Alert kind="success"><strong>{r.winner.document_code}</strong> wins. {r.reason}</Alert>}
    </div>
  )
}

function WebhooksView() {
  const { can } = useAuth()
  const q = useQuery(() => webhooks.getConfig())
  const [slackUrl, setSlackUrl] = useState('')
  const [teamsUrl, setTeamsUrl] = useState('')
  const [customUrl, setCustomUrl] = useState('')
  const [events, setEvents] = useState<string[]>([
    'PLAN_VERIFIED',
    'BEHIND_SCHEDULE_ALERT',
    'CERTIFICATE_ISSUED',
    'POLICY_UPDATED',
  ])
  const [testProvider, setTestProvider] = useState<'slack' | 'teams' | 'generic'>('slack')
  const [testUrl, setTestUrl] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    if (q.data) {
      setSlackUrl(q.data.slack_url || '')
      setTeamsUrl(q.data.teams_url || '')
      setCustomUrl(q.data.custom_url || '')
      if (q.data.enabled_events) setEvents(q.data.enabled_events)
      setTestUrl(q.data.slack_url || q.data.teams_url || q.data.custom_url || '')
    }
  }, [q.data])

  const save = useAction(
    () =>
      webhooks.updateConfig({
        slack_url: slackUrl,
        teams_url: teamsUrl,
        custom_url: customUrl,
        enabled_events: events,
      }),
    'Webhook integration parameters saved successfully'
  )

  const toggleEvent = (ev: string) => {
    setEvents((prev) => (prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]))
  }

  const handleTest = async () => {
    if (!testUrl) return
    setTesting(true)
    setTestResult(null)
    try {
      const res = await webhooks.test({ webhook_url: testUrl, provider: testProvider })
      setTestResult(res as { success: boolean; message: string })
    } catch (e: any) {
      setTestResult({ success: false, message: e.message || 'Failed to dispatch test card' })
    } finally {
      setTesting(false)
    }
  }

  if (!q.data) return <Spinner label="Loading webhook configurations..." />

  const allEvents = [
    { id: 'PLAN_VERIFIED', label: 'Plan Verified', desc: 'Fires when a new hire curriculum passes all deterministic guardrails' },
    { id: 'BEHIND_SCHEDULE_ALERT', label: 'Behind Schedule Alert', desc: 'Fires when an employee falls behind target onboarding timeline' },
    { id: 'CERTIFICATE_ISSUED', label: 'Certificate Issued', desc: 'Dispatches signed credential payload upon curriculum completion' },
    { id: 'POLICY_UPDATED', label: 'Policy Document Updated', desc: 'Notifies when new SOP revisions override existing requirements' },
  ]

  return (
    <div className="stack gap-lg">
      <Card
        title={
          <div className="row gap-sm items-center">
            <Webhook size={18} style={{ color: 'var(--primary, #3b82f6)' }} />
            <span>Organizational Webhook Endpoints</span>
          </div>
        }
        subtitle="SkillSprint AI delivers structured event cards directly to your communication channels"
        actions={
          can('ADMIN') && (
            <Button
              variant="primary"
              icon={Save}
              loading={save.running}
              onClick={async () => {
                await save.run()
                q.reload()
              }}
            >
              Save endpoints
            </Button>
          )
        }
      >
        <div className="stack gap-md">
          <div>
            <label className="label">Slack Incoming Webhook URL</label>
            <input
              type="text"
              className="input font-mono small"
              placeholder="https://hooks.slack.com/services/T00/B00/XXXX"
              value={slackUrl}
              onChange={(e) => {
                setSlackUrl(e.target.value)
                if (testProvider === 'slack') setTestUrl(e.target.value)
              }}
              disabled={!can('ADMIN')}
            />
            <div className="small muted" style={{ marginTop: 4 }}>
              Receives Rich Slack Block-Kit formatted cards with employee progress summaries and actionable buttons.
            </div>
          </div>

          <div>
            <label className="label">Microsoft Teams Incoming Webhook URL</label>
            <input
              type="text"
              className="input font-mono small"
              placeholder="https://outlook.office.com/webhook/..."
              value={teamsUrl}
              onChange={(e) => {
                setTeamsUrl(e.target.value)
                if (testProvider === 'teams') setTestUrl(e.target.value)
              }}
              disabled={!can('ADMIN')}
            />
            <div className="small muted" style={{ marginTop: 4 }}>
              Delivers Adaptive Cards directly to designated Teams channels for manager alerts.
            </div>
          </div>

          <div>
            <label className="label">Custom JSON Webhook (Generic)</label>
            <input
              type="text"
              className="input font-mono small"
              placeholder="https://api.yourcompany.com/skillsprint/events"
              value={customUrl}
              onChange={(e) => setCustomUrl(e.target.value)}
              disabled={!can('ADMIN')}
            />
          </div>
        </div>
      </Card>

      {/* Event Subscriptions */}
      <Card
        title="Active Event Triggers"
        subtitle="Select which platform events dispatch webhook notifications"
      >
        <div className="grid grid-2" style={{ gap: 12 }}>
          {allEvents.map((ev) => (
            <label
              key={ev.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12,
                padding: 12,
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: events.includes(ev.id) ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                cursor: can('ADMIN') ? 'pointer' : 'default',
              }}
            >
              <input
                type="checkbox"
                checked={events.includes(ev.id)}
                onChange={() => toggleEvent(ev.id)}
                disabled={!can('ADMIN')}
                style={{ marginTop: 3 }}
              />
              <div>
                <div className="strong" style={{ fontSize: 13 }}>{ev.label}</div>
                <div className="small muted" style={{ marginTop: 2 }}>{ev.desc}</div>
              </div>
            </label>
          ))}
        </div>
      </Card>

      {/* Live Test Runner */}
      <Card
        title={
          <div className="row gap-sm items-center">
            <Send size={18} style={{ color: 'var(--accent, #a855f7)' }} />
            <span>Test Webhook Dispatch</span>
          </div>
        }
        subtitle="Verify that your organizational webhook channel is active and receiving cards"
      >
        <div className="stack gap-sm">
          <div className="row wrap gap-sm">
            <select
              className="input"
              style={{ width: 150 }}
              value={testProvider}
              onChange={(e) => {
                const p = e.target.value as 'slack' | 'teams' | 'generic'
                setTestProvider(p)
                if (p === 'slack') setTestUrl(slackUrl)
                else if (p === 'teams') setTestUrl(teamsUrl)
                else setTestUrl(customUrl)
              }}
            >
              <option value="slack">Slack</option>
              <option value="teams">MS Teams</option>
              <option value="generic">Generic JSON</option>
            </select>
            <input
              type="text"
              className="input font-mono small"
              style={{ flex: 1, minWidth: 260 }}
              placeholder="Target webhook URL..."
              value={testUrl}
              onChange={(e) => setTestUrl(e.target.value)}
            />
            <Button
              variant="primary"
              icon={Send}
              loading={testing}
              disabled={!testUrl || !can('ADMIN')}
              onClick={handleTest}
            >
              Dispatch test card
            </Button>
          </div>

          {testResult && (
            <div style={{ marginTop: 10 }}>
              {testResult.success ? (
                <Alert kind="success">
                  <div className="row gap-sm items-center">
                    <CheckCircle2 size={16} />
                    <span><strong>Delivery Successful!</strong> {testResult.message}</span>
                  </div>
                </Alert>
              ) : (
                <Alert kind="error">
                  <strong>Delivery Failed:</strong> {testResult.message}
                </Alert>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

