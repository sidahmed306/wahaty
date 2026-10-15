import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setLogoutHandler, tokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokens.access))

  const loadMe = useCallback(async () => {
    if (!tokens.access) {
      setUser(null)
      setLoading(false)
      return null
    }
    try {
      const me = await api('/api/auth/me/')
      setUser(me)
      return me
    } catch {
      tokens.clear()
      setUser(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLogoutHandler(() => setUser(null))
    loadMe()
  }, [loadMe])

  const login = useCallback(
    async (phone, password) => {
      const data = await api('/api/auth/login/', {
        method: 'POST',
        body: { phone, password },
        auth: false,
      })
      tokens.set(data)
      return loadMe()
    },
    [loadMe],
  )

  const logout = useCallback(async () => {
    const refresh = tokens.refresh
    try {
      if (refresh) await api('/api/auth/logout/', { method: 'POST', body: { refresh } })
    } catch {
      // Déconnexion locale quoi qu'il arrive.
    }
    tokens.clear()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      reload: loadMe,
      setUser,
      hasRole: (role) => Boolean(user?.roles?.includes(role)),
    }),
    [user, loading, login, logout, loadMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
