import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { setUnauthorizedHandler, tokenStore, type Json } from '../api/client'
import { auth as authApi } from '../api/endpoints'

export type UserType = 'ADMIN' | 'TRAINING_MANAGER' | 'REVIEWER' | 'MANAGER' | 'EMPLOYEE'
export type User = { id: string; email: string; full_name: string; user_type: UserType }

type AuthState = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  can: (...types: UserType[]) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export const STAFF: UserType[] = ['ADMIN', 'TRAINING_MANAGER', 'REVIEWER', 'MANAGER']
export const GENERATORS: UserType[] = ['ADMIN', 'TRAINING_MANAGER']
export const REVIEWERS: UserType[] = ['ADMIN', 'TRAINING_MANAGER', 'REVIEWER']

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    if (!tokenStore.get()) {
      setLoading(false)
      return
    }
    authApi
      .me()
      .then((u: Json) => setUser(u))
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authApi.login(email, password)
    tokenStore.set(access_token)
    setUser(await authApi.me())
  }, [])

  const can = useCallback((...types: UserType[]) => !!user && types.includes(user.user_type), [user])

  return <AuthContext.Provider value={{ user, loading, login, logout, can }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
