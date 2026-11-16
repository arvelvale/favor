import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { api, setUnauthorizedHandler, type User } from './lib/api'
import Workbench from './components/Workbench'
import { ToastProvider } from './components/ui'
import LandingPage from './pages/Landing'
import AuthPage from './pages/Auth'
import OverviewPage from './pages/Overview'
import ChatPage from './pages/Chat'
import TrendsPage from './pages/Trends'
import RecordsPage from './pages/Records'
import ProfilePage from './pages/Profile'

interface AuthState {
  user: User | null
  llmEnabled: boolean
  setUser: (u: User | null) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState>(null!)
export const useAuth = () => useContext(AuthContext)

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [llmEnabled, setLlmEnabled] = useState(true)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    Promise.allSettled([
      api.get<{ user: User }>('/api/auth/me').then(r => setUser(r.user)),
      api.get<{ llm_enabled: boolean }>('/api/meta').then(r => setLlmEnabled(r.llm_enabled)),
    ]).finally(() => setReady(true))
  }, [])

  const logout = useCallback(async () => {
    await api.post('/api/auth/logout').catch(() => undefined)
    setUser(null)
  }, [])

  if (!ready) return <div className="loading-screen">正在加载…</div>
  return <AuthContext.Provider value={{ user, llmEnabled, setUser, logout }}>{children}</AuthContext.Provider>
}

function Protected({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function AuthGate({ mode }: { mode: 'login' | 'register' }) {
  const { user } = useAuth()
  return user ? <Navigate to="/app" replace /> : <AuthPage initialMode={mode} />
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<AuthGate mode="login" />} />
            <Route path="/register" element={<AuthGate mode="register" />} />
            <Route path="/app" element={<Protected><Workbench /></Protected>}>
              <Route index element={<OverviewPage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="chat/:id" element={<ChatPage />} />
              <Route path="trends" element={<TrendsPage />} />
              <Route path="records" element={<RecordsPage />} />
              <Route path="profile" element={<ProfilePage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
