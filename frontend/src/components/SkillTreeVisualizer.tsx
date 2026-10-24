import { useState, useEffect } from 'react'
import { GitCommit, Filter } from 'lucide-react'
import { matrix } from '../api/endpoints'
import { Spinner } from './ui'

type SkillNode = {
  id: string
  label: string
  full_statement: string
  competency: string
  priority: string
  is_mandatory: boolean
  requirement_type: string
  deadline_days: number | null
  tier: number
  source_doc: string
  source_section: string | null
  prerequisites: string[]
}

type SkillTreeData = {
  role_title: string
  role_code: string
  total_nodes: number
  total_edges: number
  max_tier: number
  competencies: string[]
  nodes: SkillNode[]
  edges: { id: string; source: string; target: string; label: string }[]
}

export function SkillTreeVisualizer({ roleId, roleTitle }: { roleId: string; roleTitle: string }) {
  const [data, setData] = useState<SkillTreeData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<SkillNode | null>(null)
  const [filterComp, setFilterComp] = useState<string>('ALL')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    matrix.skillTree(roleId)
      .then((res: any) => {
        if (active) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err: any) => {
        if (active) {
          setError(err?.message || 'Failed to load skill tree')
          setLoading(false)
        }
      })
    return () => { active = false }
  }, [roleId])

  if (loading) return <div className="center pad"><Spinner label="Generating Skill Tree DAG graph…" /></div>
  if (error || !data) return <div className="alert alert-error">{error || 'Skill tree data unavailable.'}</div>

  const filteredNodes = filterComp === 'ALL'
    ? data.nodes
    : data.nodes.filter((n) => n.competency === filterComp)

  // Group by tier
  const tiers = Array.from({ length: (data.max_tier || 0) + 1 }, (_, i) => i)
  const tierLabels = ['Tier 0 · Company Foundations', 'Tier 1 · Core Role Practices', 'Tier 2 · Advanced & Specialized', 'Tier 3 · Mastery & Leadership']

  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="card-head">
        <div>
          <div className="card-title" style={{ fontSize: 16 }}>
            <GitCommit size={18} style={{ color: 'var(--accent)' }} />
            Interactive Skill Tree & Prerequisite DAG
          </div>
          <div className="card-sub">
            {roleTitle} · {data.total_nodes} Requirements · {data.total_edges} Topological Dependencies
          </div>
        </div>

        {/* Competency Filter Chips */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <Filter size={13} /> Competency:
          </span>
          <button
            className={`btn btn-sm ${filterComp === 'ALL' ? 'btn-primary' : ''}`}
            onClick={() => setFilterComp('ALL')}
            style={{ height: 28, fontSize: 11.5 }}
          >
            All ({data.nodes.length})
          </button>
          {data.competencies.slice(0, 4).map((c) => (
            <button
              key={c}
              className={`btn btn-sm ${filterComp === c ? 'btn-primary' : ''}`}
              onClick={() => setFilterComp(c)}
              style={{ height: 28, fontSize: 11.5 }}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="card-body" style={{ background: 'var(--bg)', overflowX: 'auto', padding: '24px 20px' }}>
        <div style={{ display: 'flex', gap: 32, minWidth: 860, alignItems: 'flex-start' }}>
          {tiers.map((tierNum) => {
            const tierNodes = filteredNodes.filter((n) => n.tier === tierNum)
            if (!tierNodes.length && filterComp !== 'ALL') return null

            return (
              <div key={tierNum} style={{ flex: 1, minWidth: 260, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    fontSize: 12,
                    fontWeight: 700,
                    color: 'var(--accent-text)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>{tierLabels[tierNum] || `Tier ${tierNum}`}</span>
                  <span className="badge badge-neutral" style={{ fontSize: 10 }}>{tierNodes.length}</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {tierNodes.map((node) => {
                    const isSelected = selectedNode?.id === node.id
                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        style={{
                          background: isSelected ? 'var(--accent-soft)' : 'var(--surface)',
                          border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '12px 14px',
                          cursor: 'pointer',
                          boxShadow: isSelected ? 'var(--shadow-glow)' : 'var(--shadow-sm)',
                          transition: 'all 0.16s ease',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 7,
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) e.currentTarget.style.borderColor = 'var(--accent)'
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) e.currentTarget.style.borderColor = 'var(--border)'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                          <span className="mono" style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-text)' }}>
                            {node.id}
                          </span>
                          <span className={`badge ${node.is_mandatory ? 'badge-good' : 'badge-neutral'}`} style={{ fontSize: 10, padding: '1px 6px' }}>
                            {node.is_mandatory ? 'Mandatory' : 'Optional'}
                          </span>
                        </div>

                        <div style={{ fontSize: 12.5, fontWeight: 550, lineHeight: 1.4, color: 'var(--text)' }}>
                          {node.label}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
                          <span>{node.competency}</span>
                          {node.prerequisites.length > 0 && (
                            <span style={{ color: 'var(--warn)', fontWeight: 600 }}>
                              {node.prerequisites.length} prereq(s)
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Selected Node Details Drawer */}
      {selectedNode && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '18px 22px', background: 'var(--surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="mono" style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent)' }}>
                  {selectedNode.id}
                </span>
                <span className={`badge ${selectedNode.is_mandatory ? 'badge-good' : 'badge-neutral'}`}>
                  {selectedNode.is_mandatory ? 'Mandatory Requirement' : 'Recommended'}
                </span>
                <span className="badge badge-info">{selectedNode.priority} Priority</span>
                <span className="badge badge-neutral">Stage: Day {selectedNode.deadline_days || 90}</span>
              </div>
              <p style={{ marginTop: 8, fontSize: 13.5, lineHeight: 1.5, color: 'var(--text)', fontWeight: 500 }}>
                {selectedNode.full_statement}
              </p>
            </div>
            <button className="btn btn-sm" onClick={() => setSelectedNode(null)}>
              Close
            </button>
          </div>

          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 10, fontSize: 12, color: 'var(--text-2)' }}>
            <div>
              <strong>Source:</strong> {selectedNode.source_doc} §{selectedNode.source_section || 'General'}
            </div>
            <div>
              <strong>Competency:</strong> {selectedNode.competency}
            </div>
            <div>
              <strong>Prerequisites:</strong>{' '}
              {selectedNode.prerequisites.length > 0
                ? selectedNode.prerequisites.map((p) => (
                    <span key={p} className="chip" style={{ fontSize: 11, padding: '1px 7px', marginLeft: 4 }}>
                      {p}
                    </span>
                  ))
                : 'None (Root Node)'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
