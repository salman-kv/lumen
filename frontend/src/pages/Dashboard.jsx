import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { SquaresFour, FilesIcon, Robot, ChartBar, SignOut, ArrowSquareOut, Compass } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { api } from '../api'
import { useAuth } from '../auth'
import { Logo, ThemeToggle } from '../components/ui'
import Tour, { TOUR_KEY } from '../components/Tour'
import Overview from './dash/Overview'
import Knowledge from './dash/Knowledge'
import Assistant from './dash/Assistant'
import Usage from './dash/Usage'

const DataCtx = createContext(null)
export const useData = () => useContext(DataCtx)

const NAV = [
  { to: '/app', end: true, label: 'Overview', Icon: SquaresFour },
  { to: '/app/knowledge', label: 'Knowledge', Icon: FilesIcon },
  { to: '/app/assistant', label: 'Assistant', Icon: Robot },
  { to: '/app/usage', label: 'Usage', Icon: ChartBar },
]

export default function Dashboard() {
  const { org, logout } = useAuth()
  const nav = useNavigate()
  const [docs, setDocs] = useState(null)
  const [limits, setLimits] = useState({ max_docs: 10, max_pages: 20, max_pdf_mb: 10 })
  const [assistant, setAssistant] = useState(null)
  const [usage, setUsage] = useState(null)
  const [tourOpen, setTourOpen] = useState(false)

  const loadDocs = useCallback(() => api('/kb/documents').then((r) => { setDocs(r.documents); setLimits(r.limits) }).catch((e) => toast.error(e.message)), [])
  const loadAssistant = useCallback(() => api('/assistant').then(setAssistant).catch((e) => toast.error(e.message)), [])
  const loadUsage = useCallback(() => api('/usage').then(setUsage).catch(() => {}), [])

  useEffect(() => { loadDocs(); loadAssistant(); loadUsage() }, [loadDocs, loadAssistant, loadUsage])
  // First visit: offer the guided tour once (skippable; replay it from "Take the tour").
  const loaded = docs !== null && !!assistant
  useEffect(() => {
    if (!loaded) return
    let seen = false
    try { seen = localStorage.getItem(TOUR_KEY) === '1' } catch { /* ignore */ }
    if (seen) return
    const t = setTimeout(() => setTourOpen(true), 900)
    return () => clearTimeout(t)
  }, [loaded])
  // Poll while any document is still being processed so stages animate live.
  const processing = docs?.some((d) => d.status === 'processing')
  useEffect(() => {
    if (!processing) return
    const t = setInterval(loadDocs, 1200)
    return () => clearInterval(t)
  }, [processing, loadDocs])

  const value = useMemo(() => ({ docs, limits, assistant, usage, setAssistant, loadDocs, loadAssistant, loadUsage }), [docs, limits, assistant, usage, loadDocs, loadAssistant, loadUsage])

  const tab = ({ isActive }) => `relative flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-colors ${isActive ? 'text-ink' : 'text-muted hover:text-ink'}`
  return (
    <DataCtx.Provider value={value}>
      <div className="min-h-[100dvh] lg:grid lg:grid-cols-[17rem_1fr]">
        <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-[100dvh] lg:border-b-0 lg:border-r">
          <div className="flex h-full flex-col px-3 py-3 lg:px-4 lg:py-6">
            <div className="flex items-center justify-between px-2"><Logo /><div className="lg:hidden"><ThemeToggle /></div></div>
            <nav aria-label="Dashboard" data-tour="nav" className="scroll-thin -mx-1 mt-3 flex gap-1 overflow-x-auto px-1 lg:mt-8 lg:flex-col">
              {NAV.map(({ to, end, label, Icon }) => (
                <NavLink key={to} to={to} end={end} className={tab}>
                  {({ isActive }) => (<>
                    {isActive && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-xl bg-accent-soft" transition={{ type: 'spring', stiffness: 400, damping: 32 }} />}
                    <Icon size={19} weight={isActive ? 'fill' : 'regular'} className={`relative ${isActive ? 'text-accent' : ''}`} /><span className="relative">{label}</span>
                  </>)}
                </NavLink>
              ))}
            </nav>
            <div className="mt-auto hidden space-y-3 lg:block">
              <button onClick={() => setTourOpen(true)} className="btn btn-ghost w-full justify-between">Take the tour <Compass size={16} /></button>
              {assistant && (
                <a href={`/a/${assistant.token}`} target="_blank" rel="noreferrer" data-tour="open-assistant" className="btn btn-ghost w-full justify-between">Open assistant <ArrowSquareOut size={16} /></a>
              )}
              <div className="rounded-2xl bg-surface-2 p-3.5">
                <p className="truncate text-sm font-semibold">{org?.name}</p>
                <p className="truncate text-xs text-muted">{org?.email}</p>
                <div className="mt-3 flex gap-2">
                  <button onClick={() => { logout(); nav('/') }} className="btn btn-ghost flex-1 !py-2 !text-[13px]"><SignOut size={15} />Log out</button>
                  <ThemeToggle className="!py-2" />
                </div>
              </div>
            </div>
          </div>
        </aside>
        <main className="min-w-0 px-4 py-6 sm:px-8 lg:py-10">
          <div className="mx-auto max-w-5xl">
            <Routes>
              <Route index element={<Overview />} />
              <Route path="knowledge" element={<Knowledge />} />
              <Route path="assistant" element={<Assistant />} />
              <Route path="usage" element={<Usage />} />
              <Route path="*" element={<Navigate to="/app" replace />} />
            </Routes>
            <div className="mt-10 flex items-center justify-between border-t border-line pt-5 text-sm text-muted lg:hidden">
              <span className="truncate">{org?.name}</span>
              <button onClick={() => setTourOpen(true)} className="inline-flex items-center gap-1.5 font-semibold hover:text-ink"><Compass size={15} />Take the tour</button>
              <button onClick={() => { logout(); nav('/') }} className="inline-flex items-center gap-1.5 font-semibold hover:text-ink"><SignOut size={15} />Log out</button>
            </div>
          </div>
        </main>
      </div>
      <Tour open={tourOpen} onClose={() => setTourOpen(false)} />
    </DataCtx.Provider>
  )
}

export function PageHeader({ title, children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }} className="mb-8">
      <h1 className="text-3xl font-semibold tracking-tighter">{title}</h1>
      {children && <p className="mt-1.5 max-w-[60ch] text-muted">{children}</p>}
    </motion.div>
  )
}
