import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import LoginPage      from './pages/LoginPage'
import RegisterPage   from './pages/RegisterPage'
import DashboardPage  from './pages/DashboardPage'
import UploadPage     from './pages/UploadPage'
import ResultsPage    from './pages/ResultsPage'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' }}>
      <div className="spinner" />
    </div>
  )
  return user ? children : <Navigate to="/login" replace />
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <Navigate to="/dashboard" replace /> : children
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login"    element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
          <Route path="/dashboard" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
          <Route path="/upload"    element={<PrivateRoute><UploadPage /></PrivateRoute>} />
          <Route path="/documents/:id" element={<PrivateRoute><ResultsPage /></PrivateRoute>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
