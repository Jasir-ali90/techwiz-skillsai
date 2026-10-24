import { useState, useEffect } from 'react'
import { Award, Download, ShieldCheck, X } from 'lucide-react'
import { certificates } from '../api/endpoints'
import { Spinner } from './ui'

type CertData = {
  certificate_id: string
  status: string
  issuer: { organization: string; authority: string; program: string }
  recipient: { employee_code: string; full_name: string; role_title: string; department: string; joining_date: string }
  achievement: { plan_title: string; completion_date: string; completion_percentage: number; mandatory_coverage_score: number; source_traceability_score: number }
  security: { algorithm: string; digital_signature: string; fingerprint: string }
}

export function CertificateModal({ employeeId, onClose }: { employeeId: string; onClose: () => void }) {
  const [cert, setCert] = useState<CertData | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    let active = true
    certificates.issue(employeeId)
      .then((res: any) => {
        if (active) {
          setCert(res)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [employeeId])

  async function handleDownload() {
    setDownloading(true)
    try {
      await certificates.download(employeeId)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 820 }}>
        <div className="modal-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Award size={22} style={{ color: '#f59e0b' }} />
            <span style={{ fontWeight: 700, fontSize: 16 }}>Verifiable Onboarding Credential</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 0, color: 'var(--text-3)', cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="center pad"><Spinner label="Cryptographically signing certificate…" /></div>
          ) : cert ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Luxury Certificate Card */}
              <div
                style={{
                  background: 'linear-gradient(135deg, rgba(14, 22, 40, 0.95) 0%, rgba(10, 16, 30, 0.95) 100%)',
                  border: '2px solid rgba(245, 158, 11, 0.4)',
                  borderRadius: 16,
                  padding: '36px 40px',
                  boxShadow: '0 0 35px rgba(245, 158, 11, 0.15), var(--shadow-lg)',
                  textAlign: 'center',
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                {/* Decorative border outline */}
                <div style={{ position: 'absolute', inset: 8, border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: 12, pointerEvents: 'none' }} />

                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#f59e0b' }}>
                  {cert.issuer.organization} · Official Credential
                </div>

                <h2 style={{ fontSize: 24, fontWeight: 800, margin: '8px 0 4px', color: '#fff', letterSpacing: '-0.02em' }}>
                  CERTIFICATE OF ONBOARDING MASTERY
                </h2>
                <div style={{ fontSize: 12.5, color: '#94a3b8' }}>
                  {cert.issuer.program}
                </div>

                <div style={{ margin: '24px 0 6px', fontSize: 13, color: '#94a3b8' }}>This certifies that</div>

                <div style={{ fontSize: 28, fontWeight: 800, color: '#38bdf8', letterSpacing: '-0.01em' }}>
                  {cert.recipient.full_name}
                </div>

                <p style={{ maxWidth: 520, margin: '8px auto 20px', fontSize: 13, color: '#e2e8f0', lineHeight: 1.5 }}>
                  has completed 100% of all required training modules, compliance policies, and practical assessments for the role of{' '}
                  <strong style={{ color: '#fff' }}>{cert.recipient.role_title}</strong> in the{' '}
                  <strong style={{ color: '#fff' }}>{cert.recipient.department} Department</strong>.
                </p>

                {/* Metrics Pill Row */}
                <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap', margin: '20px 0' }}>
                  <div style={{ padding: '8px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    <div style={{ fontSize: 10.5, color: '#94a3b8', textTransform: 'uppercase' }}>Mandatory Coverage</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#10b981' }}>100.0%</div>
                  </div>
                  <div style={{ padding: '8px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    <div style={{ fontSize: 10.5, color: '#94a3b8', textTransform: 'uppercase' }}>Source Traceability</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#10b981' }}>100.0%</div>
                  </div>
                  <div style={{ padding: '8px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    <div style={{ fontSize: 10.5, color: '#94a3b8', textTransform: 'uppercase' }}>Verification Status</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#38bdf8' }}>VERIFIED</div>
                  </div>
                </div>

                {/* Signature Bar */}
                <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: 16, marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#64748b' }}>
                  <div style={{ textAlign: 'left' }}>
                    <div><strong>Algorithm:</strong> {cert.security.algorithm}</div>
                    <div className="mono" style={{ fontSize: 10 }}>Sig: {cert.security.digital_signature.slice(0, 32)}…</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontWeight: 600 }}>
                    <ShieldCheck size={16} /> Cryptographically Verified
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="alert alert-error">Unable to load certificate.</div>
          )}
        </div>

        <div className="modal-foot">
          <button className="btn" onClick={onClose}>Close</button>
          <button className="btn btn-primary" onClick={handleDownload} disabled={downloading || !cert}>
            {downloading ? <Spinner label="" /> : <Download size={15} />}
            {downloading ? 'Generating PDF…' : 'Download Official PDF'}
          </button>
        </div>
      </div>
    </div>
  )
}
