import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api, getToken, setToken } from './api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [org, setOrg] = useState(null)
  const [ready, setReady] = useState(!getToken())

  useEffect(() => {
    if (!getToken()) return
    api('/auth/me').then(setOrg).catch(() => setToken(null)).finally(() => setReady(true))
  }, [])
  useEffect(() => {
    const h = () => setOrg(null)
    window.addEventListener('kda:logout', h)
    return () => window.removeEventListener('kda:logout', h)
  }, [])

  const authenticate = useCallback(async (path, body) => {
    const r = await api(path, { method: 'POST', json: body, auth: false })
    setToken(r.token); setOrg(r.org)
    return r.org
  }, [])
  const logout = useCallback(() => { setToken(null); setOrg(null) }, [])

  return <Ctx.Provider value={{ org, ready, login: (b) => authenticate('/auth/login', b), register: (b) => authenticate('/auth/register', b), logout }}>{children}</Ctx.Provider>
}
