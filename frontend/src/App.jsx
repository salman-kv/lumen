import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AuthProvider, useAuth } from './auth'
import Landing from './pages/Landing'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'

const Dashboard = lazy(() => import('./pages/Dashboard'))

function Protected({ children }) {
  const { org, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="grid min-h-[100dvh] place-items-center"><div className="skeleton h-10 w-40" /></div>
  return org ? children : <Navigate to="/login" state={{ from: loc.pathname }} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <Toaster position="top-center" richColors closeButton theme="system" toastOptions={{ style: { borderRadius: 12 } }} />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route path="/a/:token" element={<ChatPage />} />
        <Route path="/app/*" element={
          <Protected>
            <Suspense fallback={<div className="grid min-h-[100dvh] place-items-center"><div className="skeleton h-10 w-40" /></div>}>
              <Dashboard />
            </Suspense>
          </Protected>
        } />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
