import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import './Navbar.css'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <nav className="navbar">
      <div className="container navbar-inner">
        <Link to="/dashboard" className="navbar-brand">
          <span className="brand-icon">⬡</span>
          <span className="brand-text">MSME <span className="brand-accent">Credit AI</span></span>
        </Link>
        <div className="navbar-links">
          <Link to="/dashboard" className={`nav-link ${location.pathname === '/dashboard' ? 'active' : ''}`}>Dashboard</Link>
          <Link to="/upload"    className={`nav-link ${location.pathname === '/upload' ? 'active' : ''}`}>Upload</Link>
        </div>
        <div className="navbar-right">
          <span className="user-pill">{user?.full_name?.split(' ')[0] || user?.email}</span>
          <button onClick={handleLogout} className="btn btn-ghost" id="logout-btn">Logout</button>
        </div>
      </div>
    </nav>
  )
}
