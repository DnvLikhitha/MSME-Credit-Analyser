import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import api from '../api/client'
import './DashboardPage.css'

const STATUS_ORDER = ['PENDING','EXTRACTING','SCORING','RECOMMENDING','REPORTING','COMPLETE','FAILED']

function StatusBadge({ status }) {
  const cls = `badge badge-${status?.toLowerCase() || 'pending'}`
  const dot = status === 'COMPLETE' ? '●' : status === 'FAILED' ? '✕' : '◌'
  return <span className={cls}>{dot} {status || 'PENDING'}</span>
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' })
}

export default function DashboardPage() {
  const [docs, setDocs]     = useState([])
  const [loading, setLoading] = useState(true)

  const fetchDocs = () => {
    api.get('/documents/').then(r => setDocs(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchDocs()
    // Poll every 5s if any doc is still processing
    const id = setInterval(() => {
      setDocs(d => {
        const processing = d.some(x => !['COMPLETE','FAILED'].includes(x.status))
        if (processing) fetchDocs()
        return d
      })
    }, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="page">
      <Navbar />
      <main className="container dashboard-main">
        <div className="dashboard-header fade-up">
          <div>
            <h2 className="page-title">Document Dashboard</h2>
            <p className="page-subtitle">Upload financial documents to get instant credit assessments.</p>
          </div>
          <Link to="/upload" id="upload-btn" className="btn btn-primary btn-lg">+ Upload Document</Link>
        </div>

        {loading ? (
          <div className="dash-loader"><div className="spinner" /><span>Loading documents...</span></div>
        ) : docs.length === 0 ? (
          <div className="empty-state fade-up">
            <div className="empty-icon">📄</div>
            <h3>No documents yet</h3>
            <p>Upload a GST return, bank statement, or ITR to get started.</p>
            <Link to="/upload" className="btn btn-primary">Upload your first document</Link>
          </div>
        ) : (
          <div className="doc-grid fade-up">
            {docs.map(doc => (
              <Link to={`/documents/${doc.id}`} key={doc.id} className="doc-card" id={`doc-${doc.id}`}>
                <div className="doc-card-top">
                  <div className="doc-icon">📄</div>
                  <StatusBadge status={doc.status} />
                </div>
                <div className="doc-name" title={doc.original_filename}>{doc.original_filename}</div>
                <div className="doc-meta">
                  <span>{doc.document_type}</span>
                  <span>{fmtDate(doc.created_at)}</span>
                </div>
                {!['COMPLETE','FAILED','PENDING'].includes(doc.status) && (
                  <div className="doc-progress">
                    <div className="progress-bar">
                      <div className="progress-fill pulse" style={{
                        width: `${(STATUS_ORDER.indexOf(doc.status)/5)*100}%`
                      }} />
                    </div>
                    <span className="doc-progress-label">Processing…</span>
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
