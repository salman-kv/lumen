import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import confetti from 'canvas-confetti'
import { Check, ArrowRight, UploadSimple, ChatsCircle, Code, FilePdf, Question } from '@phosphor-icons/react'
import { useData, PageHeader } from '../Dashboard'
import { useAuth } from '../../auth'
import { CountUp } from '../../components/ui'

function Step({ n, done, title, text, to, cta, Icon, active }) {
  return (
    <motion.li layout className={`relative flex gap-4 rounded-2xl border p-4 transition-colors sm:p-5 ${active ? 'border-accent bg-accent-soft/50' : 'border-line bg-surface'}`}>
      <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${done ? 'bg-accent text-accent-ink' : 'bg-surface-2 text-muted'}`}>
        {done ? <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 400, damping: 14 }}><Check size={20} weight="bold" /></motion.span> : <Icon size={20} />}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="font-semibold tracking-tight">{title}</h3>
        <p className="mt-0.5 text-sm text-muted">{text}</p>
      </div>
      <Link to={to} className={`btn self-center ${done ? 'btn-ghost' : 'btn-primary'} !py-2`}>{done ? 'Review' : cta}<ArrowRight size={15} weight="bold" className="hidden sm:block" /></Link>
    </motion.li>
  )
}

export default function Overview() {
  const { org } = useAuth()
  const { docs, limits, usage, assistant } = useData()
  const [embedded, setEmbedded] = useState(false)
  const hasDoc = !!docs?.some((d) => d.status === 'ready')
  const asked = (usage?.asked ?? 0) > 0

  useEffect(() => { try { setEmbedded(localStorage.getItem(`kda_embed_${org.id}`) === '1') } catch { /* ignore */ } }, [org.id])
  useEffect(() => {
    if (!hasDoc) return
    try {
      const k = `kda_confetti_${org.id}`
      if (localStorage.getItem(k)) return
      localStorage.setItem(k, '1')
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
        confetti({ particleCount: 110, spread: 75, origin: { y: 0.35 }, colors: ['#2fc79e', '#0b8f6e', '#dff3ec', '#e9f0ec'], disableForReducedMotion: true })
      }
    } catch { /* ignore */ }
  }, [hasDoc, org.id])

  const steps = [
    { done: hasDoc, title: 'Add your knowledge', text: 'Upload up to 10 PDFs. We index every page so answers can cite them.', to: '/app/knowledge', cta: 'Upload PDFs', Icon: UploadSimple },
    { done: asked, title: 'Try your assistant', text: 'Ask it a policy question and open "How I decided" to see each decision.', to: '/app/assistant', cta: 'Open preview', Icon: ChatsCircle },
    { done: embedded, title: 'Put it on your site', text: 'Copy the embed code or share the link. Visitors need no account.', to: '/app/assistant', cta: 'Get embed code', Icon: Code },
  ]
  const firstOpen = steps.findIndex((s) => !s.done)
  const doneCount = steps.filter((s) => s.done).length

  const loading = !docs || !usage
  const tiles = [
    { label: 'Documents', value: docs?.length ?? 0, sub: `of ${limits.max_docs} allowed`, Icon: FilePdf },
    { label: 'Questions asked', value: usage?.asked ?? 0, sub: `${usage?.answered ?? 0} answered`, Icon: ChatsCircle },
    { label: 'Needs a human', value: usage?.unable ?? 0, sub: 'not in the documents', Icon: Question },
  ]
  return (
    <>
      <PageHeader title={`Welcome, ${org.name}`}>Three steps from PDFs to a live assistant. Your progress is saved automatically.</PageHeader>

      <div className="mb-3 flex items-center justify-between text-sm"><span className="font-semibold">Getting started</span><span className="text-muted">{doneCount} of 3 done</span></div>
      <div className="mb-5 h-1.5 overflow-hidden rounded-full bg-line"><motion.div className="h-full rounded-full bg-accent" animate={{ width: `${(doneCount / 3) * 100}%` }} transition={{ type: 'spring', stiffness: 120, damping: 20 }} /></div>
      <ol className="space-y-3">{steps.map((s, i) => <Step key={s.title} n={i + 1} active={i === firstOpen} {...s} />)}</ol>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {tiles.map(({ label, value, sub, Icon }, i) => (
          <motion.div key={label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.07 }} className="card p-5">
            <div className="flex items-center justify-between text-muted"><span className="text-sm font-medium">{label}</span><Icon size={18} /></div>
            {loading ? <div className="skeleton mt-3 h-9 w-16" /> : <p className="mt-2 text-4xl font-semibold tracking-tighter"><CountUp value={value} /></p>}
            <p className="mt-1 text-sm text-muted">{sub}</p>
          </motion.div>
        ))}
      </div>
      {assistant && (
        <p className="mt-8 text-sm text-muted">Your public assistant link: <Link to="/app/assistant" className="font-mono text-ink underline-offset-2 hover:underline">{assistant.url.replace(/^https?:\/\//, '').slice(0, 44)}...</Link></p>
      )}
    </>
  )
}
