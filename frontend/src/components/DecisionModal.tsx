import { useState } from 'react'
import { Check, MessageSquare, PenLine, RefreshCw, X, type LucideIcon } from 'lucide-react'
import type { Json } from '../api/client'
import { review } from '../api/endpoints'
import { useAction } from '../lib/hooks'
import { Alert, Badge, Button, Field, JsonEditor, JsonView, KeyValue, Modal, humanize } from './ui'

const DECISIONS: { id: string; label: string; icon: LucideIcon; hint: string }[] = [
  { id: 'APPROVE', label: 'Approve', icon: Check, hint: 'The item is fine as it is. The finding is closed; the original check result is kept.' },
  { id: 'REJECT', label: 'Reject', icon: X, hint: 'The problem is real. The item stays flagged.' },
  { id: 'EDIT', label: 'Edit', icon: PenLine, hint: 'Correct the item yourself, then run the quality check again.' },
  { id: 'REGENERATE', label: 'Rewrite with AI', icon: RefreshCw, hint: 'Ask the AI to rewrite the module this item belongs to.' },
  { id: 'COMMENT', label: 'Comment', icon: MessageSquare, hint: 'Leave a note. The finding stays open.' },
]

/** Plan items the backend lets a reviewer edit (review_service.EDITABLE). */
const EDITABLE_TYPES = new Set(['module', 'checklist_item', 'task', 'quiz_question', 'assessment'])

type Props = { finding: Json | null; onClose: () => void; onDone: () => void }

/** Reviewer decision on one finding (SRS Steps 48-49). Every decision is append-only.
 * Keyed by finding so the choice and reason never carry over to the next item. */
export function DecisionModal({ finding, ...rest }: Props) {
  if (!finding) return null
  return <DecisionDialog key={finding.id} finding={finding} {...rest} />
}

function DecisionDialog({ finding, onClose, onDone }: Props & { finding: Json }) {
  const [decision, setDecision] = useState('APPROVE')
  const [reason, setReason] = useState('')
  const [edits, setEdits] = useState<Json>({})
  const [editsValid, setEditsValid] = useState(true)
  const act = useAction(
    () => review.decide(finding.id, { decision, reason, edits: decision === 'EDIT' ? edits : undefined }),
    (r: Json) => `Decision saved. The item is now ${humanize(r.review_status).toLowerCase()}.`,
  )
  const template: Json = finding.item_type === 'task' ? { description: '' } : finding.item_type === 'checklist_item' ? { activity: '' } : finding.item_type === 'quiz_question' ? { question: '', correct_answer: [] } : { title: '' }
  // Findings about a document (e.g. a contradiction) have no plan item to edit,
  // and rewriting needs a requirement, so only offer what the backend accepts.
  const canEdit = EDITABLE_TYPES.has(finding.item_type) && !!finding.item_id
  const canRegenerate = !!finding.requirement_code || canEdit
  const options = DECISIONS.filter((d) => (d.id !== 'EDIT' || canEdit) && (d.id !== 'REGENERATE' || canRegenerate))
  const chosen = options.find((d) => d.id === decision) ?? options[0]

  return (
    <Modal
      open
      wide
      title="Review flagged item"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            icon={chosen.icon}
            loading={act.running}
            disabled={reason.trim().length < 3 || (decision === 'EDIT' && !editsValid)}
            title={reason.trim().length < 3 ? 'Add a short reason first' : undefined}
            onClick={async () => {
              if (await act.run()) {
                onDone()
                onClose()
              }
            }}
          >
            {chosen.label}
          </Button>
        </>
      }
    >
      <div className="stack">
        <Alert kind="warn">
          <div className="row gap-sm wrap" style={{ marginBottom: 4 }}><Badge value={finding.severity} /> <span className="small strong">{humanize(finding.rule)}</span></div>
          <div>{finding.message}</div>
        </Alert>
        <KeyValue
          items={[
            ['Item', `${humanize(finding.item_type ?? '—')}${finding.item_id ? ` (${finding.item_id.slice(0, 8)})` : ''}`],
            ['Requirement', finding.requirement_code],
            ['Current status', <Badge value={finding.item_status} />],
          ]}
        />
        <JsonView value={finding.evidence} collapsed label="evidence" />
        <Field label="Your decision">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
            {options.map((d) => (
              <button
                key={d.id}
                type="button"
                className="demo"
                aria-pressed={decision === d.id}
                style={decision === d.id ? { borderColor: 'var(--accent)', background: 'var(--accent-soft)', color: 'var(--accent-text)' } : undefined}
                onClick={() => setDecision(d.id)}
              >
                <d.icon size={16} style={{ marginLeft: 0, color: 'inherit' }} />
                <span className="strong small">{d.label}</span>
              </button>
            ))}
          </div>
          <span className="field-hint">{chosen.hint}</span>
        </Field>
        {decision === 'EDIT' && (
          <Field label="Fields to change" hint="JSON with the fields of this item, e.g. description, due_stage or source_chunk_code.">
            <JsonEditor initial={template} resetKey={finding.id} rows={6} onChange={(v, ok) => { setEditsValid(ok); if (ok) setEdits(v) }} />
          </Field>
        )}
        {decision === 'REGENERATE' && <Alert kind="info">The module is rewritten by the AI. Run the quality check again afterwards.</Alert>}
        <Field label="Reason" hint="Required. Saved in the activity log so others can see why.">
          <textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Checked with the HR team: the 2026 policy applies" />
        </Field>
      </div>
    </Modal>
  )
}
