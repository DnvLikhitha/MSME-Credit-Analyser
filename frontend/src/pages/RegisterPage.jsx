import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import './AuthPages.css'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate     = useNavigate()
  const [form, setForm]   = useState({ firstName: '', lastName: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const fullName = `${form.firstName} ${form.lastName}`.trim()
      await register(form.email, form.password, fullName)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.')
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
          <h1 className="auth-title">Create account</h1>
          <p className="auth-subtitle">Start analyzing MSME credit instantly</p>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-row">
            <div className="form-group floating">
              <div className="floating-input-wrapper">
                <label className="floating-label" htmlFor="firstName">First name</label>
                <input
                  id="firstName" type="text" className="floating-input"
                  placeholder="Michal"
                  value={form.firstName} onChange={set('firstName')} required
                />
              </div>
            </div>
            <div className="form-group floating">
              <div className="floating-input-wrapper">
                <label className="floating-label" htmlFor="lastName">Last name</label>
                <input
                  id="lastName" type="text" className="floating-input"
                  placeholder="Masiak"
                  value={form.lastName} onChange={set('lastName')} required
                />
              </div>
            </div>
          </div>

          <div className="form-group floating">
            <div className="floating-input-wrapper">
              <label className="floating-label" htmlFor="reg-email">Work Email</label>
              <input
                id="reg-email" type="email" className="floating-input"
                placeholder="you@example.com"
                value={form.email} onChange={set('email')} required
              />
            </div>
          </div>

          <div className="form-group floating">
            <div className="floating-input-wrapper">
              <label className="floating-label" htmlFor="reg-password">Password</label>
              <input
                id="reg-password" type="password" className="floating-input"
                placeholder="••••••••"
                value={form.password} onChange={set('password')} required
              />
            </div>
          </div>

          <button type="submit" className="btn-auth-primary" disabled={loading}>
            {loading ? 'Creating...' : 'Create free account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in instead</Link>
        </p>

      </div>
    </div>
  )
}
