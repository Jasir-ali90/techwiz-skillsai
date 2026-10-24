import { useState, useEffect } from 'react'
import { Terminal, Play, RotateCcw, CheckCircle2, XCircle } from 'lucide-react'
import { sandbox } from '../api/endpoints'
import { Spinner } from './ui'

type Challenge = {
  id: string
  title: string
  role: string
  language: string
  difficulty: string
  summary: string
  instructions: string
  starter_code: string
}

type EvalResult = {
  passed: boolean
  score: number
  feedback: string
  passed_tests?: number
  total_tests?: number
  test_results: { test: string; passed: boolean; error?: string }[]
}

export function CodingSandbox({ roleCode = 'BACKEND_DEV', employeeId }: { roleCode?: string; employeeId?: string }) {
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [activeIdx, setActiveIdx] = useState(0)
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [result, setResult] = useState<EvalResult | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    sandbox.challenges(roleCode)
      .then((res: any) => {
        if (active && Array.isArray(res) && res.length) {
          setChallenges(res)
          setCode(res[0].starter_code)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [roleCode])

  function selectChallenge(idx: number) {
    setActiveIdx(idx)
    setCode(challenges[idx].starter_code)
    setResult(null)
  }

  async function handleRunTests() {
    if (!challenges[activeIdx] || evaluating) return
    setEvaluating(true)
    try {
      const res: any = await sandbox.evaluate({
        challenge_id: challenges[activeIdx].id,
        code,
        employee_id: employeeId,
      })
      setResult(res)
    } catch (err: any) {
      setResult({
        passed: false,
        score: 0,
        feedback: `Execution failed: ${err?.message || 'Server error'}`,
        test_results: [{ test: 'Runtime Invocation', passed: false, error: err?.message }],
      })
    } finally {
      setEvaluating(false)
    }
  }

  if (loading) return <div className="center pad"><Spinner label="Loading technical sandbox challenges…" /></div>
  if (!challenges.length) return null

  const current = challenges[activeIdx]

  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="card-head">
        <div>
          <div className="card-title" style={{ fontSize: 16 }}>
            <Terminal size={18} style={{ color: 'var(--accent)' }} />
            Practical Role Assessment Sandbox
          </div>
          <div className="card-sub">
            Hands-on technical validation evaluated deterministically by the Python verification engine
          </div>
        </div>

        {/* Challenge Tabs */}
        {challenges.length > 1 && (
          <div className="segmented">
            {challenges.map((c, i) => (
              <button
                key={c.id}
                className={activeIdx === i ? 'on' : ''}
                onClick={() => selectChallenge(i)}
              >
                {c.title.split(' ')[0]} Challenge {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ padding: '16px 22px', borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>{current.title}</h3>
          <span className="badge badge-info">{current.difficulty}</span>
          <span className="badge badge-neutral mono">{current.language.toUpperCase()}</span>
        </div>
        <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text-2)' }}>{current.summary}</p>

        <div style={{ marginTop: 10, padding: '10px 14px', background: 'var(--surface)', borderRadius: 8, border: '1px solid var(--border)', fontSize: 12.5, whiteSpace: 'pre-line' }}>
          <strong>Instructions:</strong><br />
          {current.instructions}
        </div>
      </div>

      <div className="card-body" style={{ padding: 0 }}>
        {/* Code Editor */}
        <div style={{ position: 'relative' }}>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            style={{
              width: '100%',
              minHeight: 220,
              background: '#090e1a',
              color: '#38bdf8',
              fontFamily: 'JetBrains Mono, Consolas, monospace',
              fontSize: 13,
              lineHeight: 1.6,
              padding: '16px 20px',
              border: 0,
              outline: 'none',
              resize: 'vertical',
            }}
          />
        </div>

        {/* Toolbar */}
        <div style={{ padding: '12px 20px', background: 'var(--surface-2)', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            className="btn btn-sm"
            onClick={() => {
              setCode(current.starter_code)
              setResult(null)
            }}
            title="Reset to initial starter template"
          >
            <RotateCcw size={14} /> Reset Code
          </button>

          <button
            className="btn btn-primary btn-sm"
            onClick={handleRunTests}
            disabled={evaluating}
            style={{ gap: 6 }}
          >
            {evaluating ? <Spinner label="" /> : <Play size={14} fill="currentColor" />}
            {evaluating ? 'Evaluating tests…' : 'Run Automated Tests'}
          </button>
        </div>

        {/* Results Console */}
        {result && (
          <div
            style={{
              padding: '16px 20px',
              borderTop: '1px solid var(--border)',
              background: result.passed ? 'var(--good-soft)' : 'var(--bad-soft)',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {result.passed ? (
                  <CheckCircle2 size={20} style={{ color: 'var(--good)' }} />
                ) : (
                  <XCircle size={20} style={{ color: 'var(--bad)' }} />
                )}
                <strong style={{ fontSize: 14 }}>
                  {result.passed ? 'Assessment Passed (100% Score)' : `Tests Incomplete (${result.score}% Score)`}
                </strong>
              </div>
              <span className={`badge ${result.passed ? 'badge-good' : 'badge-bad'}`}>
                {result.passed_tests || 0} / {result.total_tests || 0} Assertions Passed
              </span>
            </div>

            <p style={{ margin: '8px 0 10px', fontSize: 13, color: 'var(--text)' }}>
              {result.feedback}
            </p>

            {/* Test Case Breakdown */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {result.test_results.map((t, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 12.5,
                    padding: '4px 8px',
                    borderRadius: 6,
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                  }}
                >
                  {t.passed ? (
                    <CheckCircle2 size={14} style={{ color: 'var(--good)' }} />
                  ) : (
                    <XCircle size={14} style={{ color: 'var(--bad)' }} />
                  )}
                  <span>{t.test}</span>
                  {t.error && <span style={{ marginLeft: 'auto', color: 'var(--bad)', fontSize: 11 }}>{t.error}</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
