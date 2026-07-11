import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import './AuthPages.css'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate     = useNavigate()
  const [form, setForm]   = useState({ fullName: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await register(form.email, form.password, form.fullName)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-bg" />
      <div className="auth-card fade-up">
        <div className="auth-logo">
          <span className="auth-logo-icon">⬡</span>
          <h1 className="auth-title">Get Started</h1>
          <p className="auth-subtitle">Create your MSME Credit AI account</p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label" htmlFor="fullName">Full Name</label>
            <input
              id="fullName" type="text" className="form-input"
              placeholder="DNV Likhitha"
              value={form.fullName} onChange={set('fullName')} required
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="reg-email">Email</label>
            <input
              id="reg-email" type="email" className="form-input"
              placeholder="you@example.com"
              value={form.email} onChange={set('email')} required
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="reg-password">Password</label>
            <input
              id="reg-password" type="password" className="form-input"
              placeholder="Min 8 chars, 1 uppercase, 1 number"
              value={form.password} onChange={set('password')} required
            />
          </div>
          <button type="submit" id="register-submit" className="btn btn-primary btn-full btn-lg" disabled={loading}>
            {loading ? <><span className="spinner" />Creating account...</> : 'Create Account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" className="auth-link">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
