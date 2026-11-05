import { useEffect } from 'react'
import { motion } from 'motion/react'
import { ChatsCircle, CheckCircle, UserFocus, Scales, Timer } from '@phosphor-icons/react'
import { useData, PageHeader } from '../Dashboard'
import { CountUp } from '../../components/ui'

const OUTCOME = {
  answered: { text: 'Answered', cls: 'bg-accent-soft text-accent' },
  needs_info: { text: 'Asked for details', cls: 'bg-warn-soft text-warn' },
  no_knowledge: { text: 'Not in documents', cls: 'bg-bad-soft text-bad' },
  error: { text: 'Error', cls: 'bg-bad-soft text-bad' },
}

export default function Usage() {
  const { usage, loadUsage } = useData()
  useEffect(() => { loadUsage() }, [loadUsage])
  if (!usage) return <><PageHeader title="Usage" /><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><div className="skeleton h-28" /><div className="skeleton h-28" /><div className="skeleton h-28" /><div className="skeleton h-28" /></div></>
  const max = Math.max(1, ...usage.daily.map((d) => d.count))
  const tiles = [
    { label: 'Questions asked', value: usage.asked, Icon: ChatsCircle },
    { label: 'Answered', value: usage.answered, Icon: CheckCircle },
    { label: 'Unable to answer', value: usage.unable, Icon: UserFocus, note: 'Candidates for human review' },
    { label: 'Used decision checks', value: usage.decision_questions, Icon: Scales },
  ]
  return (
    <>
      <PageHeader title="Usage">See what visitors ask and where the documents fall short.</PageHeader>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map(({ label, value, Icon, note }, i) => (
          <motion.div key={label} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }} className="card p-5">
            <div className="flex items-center justify-between text-muted"><span className="text-sm font-medium">{label}</span><Icon size={18} /></div>
            <p className="mt-2 text-4xl font-semibold tracking-tighter"><CountUp value={value} /></p>
            {note && <p className="mt-1 text-xs text-muted">{note}</p>}
          </motion.div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <section className="card p-5 sm:p-6">
          <div className="flex items-center justify-between"><h2 className="font-semibold tracking-tight">Last 7 days</h2><span className="flex items-center gap-1.5 text-xs text-muted"><Timer size={14} />avg {(usage.avg_latency_ms / 1000).toFixed(1)}s per answer</span></div>
          <div className="mt-6 flex h-40 items-end gap-2" role="img" aria-label="Questions per day for the last 7 days">
            {usage.daily.map((d, i) => (
              <div key={d.date} className="flex flex-1 flex-col items-center gap-2">
                <div className="flex h-32 w-full items-end"><motion.div className="w-full origin-bottom rounded-lg bg-accent" style={{ height: `${Math.max((d.count / max) * 100, d.count ? 6 : 2)}%`, opacity: d.count ? 1 : 0.25 }}
                  initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ delay: 0.1 + i * 0.05, type: 'spring', stiffness: 160, damping: 18 }} title={`${d.count} questions`} /></div>
                <span className="text-[11px] text-muted">{new Date(d.date + 'T12:00').toLocaleDateString(undefined, { weekday: 'short' })}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="card p-5 sm:p-6">
          <h2 className="font-semibold tracking-tight">Recent questions</h2>
          {usage.recent.length === 0 ? (
            <div className="grid place-items-center py-10 text-center"><ChatsCircle size={36} weight="duotone" className="text-muted" /><p className="mt-2 text-sm text-muted">No questions yet. Try your assistant from the Assistant tab.</p></div>
          ) : (
            <ul className="mt-4 divide-y divide-line">
              {usage.recent.map((r, i) => {
                const o = OUTCOME[r.outcome] || OUTCOME.error
                return (
                  <motion.li key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }} className="flex items-start justify-between gap-3 py-3">
                    <p className="min-w-0 text-sm leading-snug">{r.question}</p>
                    <span className={`chip shrink-0 ${o.cls}`}>{o.text}</span>
                  </motion.li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
    </>
  )
}
