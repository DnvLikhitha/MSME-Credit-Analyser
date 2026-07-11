import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import api from '../api/client'
import './ResultsPage.css'

const PROCESSING_STATUSES = ['PENDING','EXTRACTING','SCORING','RECOMMENDING','REPORTING']

function StatusBadge({ status }) {
  return <span className={`badge badge-${status?.toLowerCase()}`}>{status}</span>
}

function ScoreGauge({ score, band }) {
  const color = band === 'LOW' ? '#22C55E' : band === 'MEDIUM' ? '#F59E0B' : '#EF4444'
  const pct   = (score / 100) * 100
  return (
    <div className="score-gauge">
      <svg viewBox="0 0 120 70" className="gauge-svg">
        <path d="M10 60 A50 50 0 0 1 110 60" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="10" strokeLinecap="round"/>
        <path d="M10 60 A50 50 0 0 1 110 60" fill="none" stroke={color}
          strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${pct * 1.57} 157`}
          style={{ transition: 'stroke-dasharray 1s ease' }}
        />
      </svg>
      <div className="gauge-score">{score?.toFixed(0)}</div>
      <div className="gauge-label">out of 100</div>
      <div className="gauge-band" style={{ color }}>{band} RISK</div>
    </div>
  )
}

function FactorBar({ factor }) {
  const pct = factor.pct || 0
  const color = pct >= 75 ? '#22C55E' : pct >= 40 ? '#F59E0B' : '#EF4444'
  return (
    <div className="factor-row">
      <div className="factor-header">
        <span className="factor-name">{factor.factor}</span>
        <span className="factor-score">{factor.score}/{factor.max}</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <p className="factor-explanation">{factor.explanation}</p>
    </div>
  )
}

function MetricRow({ label, value }) {
  return (
    <tr>
      <td>{label}</td>
      <td style={{ textAlign: 'right', fontWeight: 600, color: value === '—' ? '#566573' : 'var(--text)' }}>
        {value}
      </td>
    </tr>
  )
}

function fmtInr(v) {
  if (v == null) return '—'
  if (v >= 10000000) return `₹${(v/10000000).toFixed(2)} Cr`
  if (v >= 100000)   return `₹${(v/100000).toFixed(2)} L`
  return `₹${v.toLocaleString('en-IN')}`
}
function fmtPct(v) { return v == null ? '—' : `${v.toFixed(1)}%` }
function fmtRatio(v) { return v == null ? '—' : `${v.toFixed(2)}x` }

export default function ResultsPage() {
  const { id } = useParams()
  const [doc,   setDoc]   = useState(null)
  const [score, setScore] = useState(null)
  const [recs,  setRecs]  = useState([])
  const [report,setReport]= useState(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  const fetchAll = async () => {
    try {
      const [docRes, scoreRes, recRes, repRes] = await Promise.allSettled([
        api.get(`/documents/${id}`),
        api.get(`/documents/${id}/risk-score`),
        api.get(`/documents/${id}/recommendations`),
        api.get(`/documents/${id}/report`),
      ])
      if (docRes.status   === 'fulfilled') setDoc(docRes.value.data)
      if (scoreRes.status === 'fulfilled') setScore(scoreRes.value.data?.risk_score)
      if (recRes.status   === 'fulfilled') setRecs(recRes.value.data?.recommendations || [])
      if (repRes.status   === 'fulfilled') setReport(repRes.value.data)
    } finally { setLoading(false) }
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(() => {
      if (doc && PROCESSING_STATUSES.includes(doc.status)) fetchAll()
    }, 4000)
    return () => clearInterval(interval)
  }, [id, doc?.status])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await api.get(`/documents/${id}/report/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a   = document.createElement('a')
      a.href = url; a.download = `credit_report_${doc?.original_filename || id}.pdf`
      a.click(); URL.revokeObjectURL(url)
    } finally { setDownloading(false) }
  }

  if (loading) return (
    <div className="page">
      <Navbar />
      <div className="results-loader"><div className="spinner" /><span>Loading analysis…</span></div>
    </div>
  )

  const isProcessing = PROCESSING_STATUSES.includes(doc?.status)
  const metrics = doc?.metrics  // in case the API adds metrics to document response in future

  return (
    <div className="page">
      <Navbar />
      <main className="container results-main">
        {/* Header */}
        <div className="results-header fade-up">
          <div>
            <Link to="/dashboard" className="back-link">← Back to Dashboard</Link>
            <h2 className="page-title" title={doc?.original_filename}>{doc?.original_filename}</h2>
            <div style={{ display:'flex', gap:8, alignItems:'center', marginTop:6 }}>
              <StatusBadge status={doc?.status} />
              <span style={{ fontSize:12, color:'var(--text-muted)' }}>{doc?.document_type}</span>
            </div>
          </div>
          {report?.status === 'COMPLETE' && (
            <button id="download-report-btn" className="btn btn-primary btn-lg" onClick={handleDownload} disabled={downloading}>
              {downloading ? <><span className="spinner" />Downloading…</> : '⬇ Download PDF Report'}
            </button>
          )}
        </div>

        {/* Processing State */}
        {isProcessing && (
          <div className="processing-card card fade-up">
            <div className="processing-inner">
              <div className="spinner" style={{ width:32, height:32, borderWidth:3 }} />
              <div>
                <p className="processing-title">Analysis in progress</p>
                <p className="processing-sub">
                  {doc?.status === 'EXTRACTING'   && 'Reading and extracting financial metrics from the document...'}
                  {doc?.status === 'SCORING'       && 'Running credit risk scoring algorithm...'}
                  {doc?.status === 'RECOMMENDING' && 'Finding best matching loan schemes via AI...'}
                  {doc?.status === 'REPORTING'    && 'Generating your PDF credit report...'}
                  {doc?.status === 'PENDING'      && 'Queued — worker will pick this up shortly...'}
                </p>
              </div>
            </div>
            <div className="progress-bar" style={{ marginTop:16 }}>
              <div className="progress-fill pulse" style={{
                width: `${(['PENDING','EXTRACTING','SCORING','RECOMMENDING','REPORTING'].indexOf(doc?.status) + 1) * 20}%`
              }} />
            </div>
          </div>
        )}

        {/* Score Section */}
        {score && (
          <div className="results-grid fade-up">
            <div className="card score-card">
              <h3 className="section-title">Credit Score</h3>
              <ScoreGauge score={score.overall_score} band={score.risk_band} />
              {score.narrative_summary && (
                <p className="narrative">{score.narrative_summary}</p>
              )}
            </div>

            <div className="card factors-card">
              <h3 className="section-title">Factor Breakdown</h3>
              <div className="factors-list">
                {(score.factor_breakdown || []).map((f, i) => (
                  <FactorBar key={i} factor={f} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Recommendations */}
        {recs.length > 0 && (
          <div className="card recs-card fade-up">
            <h3 className="section-title">Recommended Loan Schemes</h3>
            <div className="recs-grid">
              {recs.map(rec => (
                <div key={rec.id} className="rec-item">
                  <div className="rec-header">
                    <span className="rec-rank">#{rec.rank}</span>
                    <span className="rec-type badge badge-complete">{rec.scheme_type}</span>
                  </div>
                  <h4 className="rec-name">{rec.scheme_name}</h4>
                  <p className="rec-body">{rec.issuing_body}</p>
                  {rec.eligibility_score != null && (
                    <div className="rec-eligibility">
                      <span>Eligibility</span>
                      <div className="progress-bar" style={{ flex:1 }}>
                        <div className="progress-fill" style={{ width:`${rec.eligibility_score*100}%` }} />
                      </div>
                      <span>{(rec.eligibility_score*100).toFixed(0)}%</span>
                    </div>
                  )}
                  {rec.scheme_details && (
                    <div className="rec-details">
                      {rec.scheme_details.max_loan_amount_inr && <span>Max: {fmtInr(rec.scheme_details.max_loan_amount_inr)}</span>}
                      {rec.scheme_details.interest_rate_range && <span>{rec.scheme_details.interest_rate_range}</span>}
                      {rec.scheme_details.collateral_required != null && (
                        <span>{rec.scheme_details.collateral_required ? 'Collateral required' : 'No collateral'}</span>
                      )}
                    </div>
                  )}
                  {rec.reasoning && <p className="rec-reasoning">{rec.reasoning}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No results yet */}
        {!isProcessing && !score && (
          <div className="card fade-up" style={{ textAlign:'center', padding:'48px', color:'var(--text-muted)' }}>
            {doc?.status === 'FAILED'
              ? <><p style={{fontSize:18,fontWeight:700,color:'var(--high)'}}>Processing Failed</p><p style={{marginTop:8}}>{doc?.error_message}</p></>
              : <p>No results available yet. Make sure the background worker is running.</p>
            }
          </div>
        )}
      </main>
    </div>
  )
}
