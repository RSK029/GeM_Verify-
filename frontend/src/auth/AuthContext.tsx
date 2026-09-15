/**
 * Session state.
 *
 * The session itself lives in an httpOnly cookie the browser manages. This
 * context holds only the User object returned by the API — nothing is written
 * to localStorage, and no token is ever read by JavaScript.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react'
import type { ReactNode } from 'react'
import { auth as authApi, setUnauthorizedHandler } from '@/api/client'
import type { User } from '@/api/types'

interface AuthState {
  user: User | null
  /** True until the boot-time GET /auth/me has resolved one way or the other. */
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (input: {
    name: string; email: string; password: string; company_name: string
  }) => Promise<User>
  logout: () => Promise<void>
  /** Set when the session expired mid-use, so /login can explain why. */
  expired: boolean
  clearExpired: () => void
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [expired, setExpired] = useState(false)
  const userRef = useRef<User | null>(null)
  userRef.current = user

  // One place handles every mid-session 401, wherever it came from.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (userRef.current) setExpired(true)
      setUser(null)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  // Boot: ask the server who we are. A 401 here is the ordinary
  // "not signed in" answer, not an expiry.
  useEffect(() => {
    let alive = true
    authApi
      .me()
      .then((u) => { if (alive) setUser(u) })
      .catch(() => { if (alive) setUser(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const u = await authApi.login(email, password)
    setUser(u)
    setExpired(false)
    return u
  }, [])

  const register = useCallback(
    async (input: {
      name: string; email: string; password: string; company_name: string
    }) => {
      const created = await authApi.register(input)
      // Registration does not open a session; sign in with the same details.
      await authApi.login(input.email, input.password)
      const me = await authApi.me()
      setUser(me)
      return created
    },
    [],
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
      setExpired(false)
    }
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user, loading, login, register, logout,
      expired, clearExpired: () => setExpired(false),
    }),
    [user, loading, login, register, logout, expired],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be used inside <AuthProvider>')
  return v
}
