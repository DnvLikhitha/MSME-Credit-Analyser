import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import api from '../api/client'
import './UploadPage.css'

const DOC_TYPES = ['BANK_STATEMENT','GST_RETURN','ITR','OTHER']

export default function UploadPage() {
  const navigate = useNavigate()
  const fileRef  = useRef()
  const [file, setFile]         = useState(null)
  const [docType, setDocType]   = useState('BANK_STATEMENT')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError]       = useState('')

  const pickFile = (f) => {
    if (!f) return
    const valid = ['application/pdf','image/jpeg','image/png'].includes(f.type)
    if (!valid) { setError('Only PDF, JPEG, or PNG files are accepted.'); return }
    setFile(f); setError('')
  }

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false)
    pickFile(e.dataTransfer.files[0])
  }

  const handleUpload = async () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    form.append('document_type', docType)
    setUploading(true); setError('')
    try {
      const { data } = await api.post('/documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      navigate(`/documents/${data.document.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page">
      <Navbar />
      <main className="container upload-main">
        <div className="upload-header fade-up">
          <h2 className="page-title">Upload Financial Document</h2>
          <p className="page-subtitle">Supported formats: PDF, JPEG, PNG · Max size: 20MB</p>
        </div>

        <div className="upload-layout fade-up">
          {/* Drop Zone */}
          <div
            className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
            onClick={() => fileRef.current.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            id="drop-zone"
          >
            <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png" hidden
              onChange={e => pickFile(e.target.files[0])} />
            {file ? (
              <div className="file-preview">
                <div className="file-icon">📄</div>
                <div className="file-name">{file.name}</div>
                <div className="file-size">{(file.size / 1024).toFixed(0)} KB</div>
                <button className="btn btn-ghost" onClick={e => { e.stopPropagation(); setFile(null) }}>Remove</button>
              </div>
            ) : (
              <div className="drop-prompt">
                <div className="drop-icon">⬆</div>
                <p className="drop-text">Drag & drop your file here</p>
                <p className="drop-sub">or click to browse</p>
              </div>
            )}
          </div>

          {/* Config Panel */}
          <div className="upload-config card">
            <h3 className="config-title">Document Settings</h3>

            <div className="form-group">
              <label className="form-label">Document Type</label>
              {DOC_TYPES.map(t => (
                <label key={t} className={`type-option ${docType === t ? 'selected' : ''}`}>
                  <input type="radio" name="docType" value={t} checked={docType === t}
                    onChange={() => setDocType(t)} hidden />
                  <span className="type-dot" />
                  <span>{t.replace('_', ' ')}</span>
                </label>
              ))}
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <button id="upload-submit" className="btn btn-primary btn-full btn-lg"
              onClick={handleUpload} disabled={!file || uploading}>
              {uploading ? <><span className="spinner" />Uploading…</> : 'Analyse Document'}
            </button>

            <p className="upload-note">
              After upload, the AI pipeline will automatically extract metrics, score credit risk, and recommend loan schemes.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
