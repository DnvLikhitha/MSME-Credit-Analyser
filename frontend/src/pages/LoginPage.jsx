import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import './AuthPages.css'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate  = useNavigate()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card fade-up">
        
        <div className="auth-header">
          <div className="auth-logo">
            <svg viewBox="0 0 24 24"><path d="M12 2L2 22h20L12 2zm0 6l5 10H7l5-10z"/></svg>
          </div>
          <h1 className="auth-title">Welcome back</h1>
          <p className="auth-subtitle">Log in to MSME Credit AI</p>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group floating">
            <div className="floating-input-wrapper">
              <label className="floating-label" htmlFor="email">Email</label>
              <input
                id="email" type="email" className="floating-input"
                placeholder="you@example.com"
                value={email} onChange={e => setEmail(e.target.value)} required
              />
            </div>
          </div>

          <div className="form-group floating">
            <div className="floating-input-wrapper">
              <label className="floating-label" htmlFor="password">Password</label>
              <input
                id="password" type="password" className="floating-input"
                placeholder="••••••••"
                value={password} onChange={e => setPassword(e.target.value)} required
              />
            </div>
          </div>

          <button type="submit" className="btn-auth-primary" disabled={loading}>
            {loading ? 'Logging in...' : 'Sign in to dashboard'}
          </button>
        </form>

        <p className="auth-footer">
          Don't have an account? <Link to="/register">Create one now</Link>
        </p>

      </div>
    </div>
  )
}
