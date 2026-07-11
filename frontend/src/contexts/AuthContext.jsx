import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      api.get('/auth/me')
        .then(r => setUser(r.data))
        .catch(() => localStorage.removeItem('token'))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    form.append('grant_type', 'password')
    const { data } = await api.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    localStorage.setItem('token', data.access_token)
    const me = await api.get('/auth/me')
    setUser(me.data)
    return me.data
  }

  const register = async (email, password, fullName) => {
    await api.post('/auth/register', { email, password, full_name: fullName })
    return login(email, password)
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
