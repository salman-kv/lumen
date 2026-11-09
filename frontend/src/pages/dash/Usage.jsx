import { useCallback, useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { ChatsCircle, CheckCircle, UserFocus, Scales, Timer, MagnifyingGlass, DownloadSimple, CaretDown, CaretLeft, CaretRight } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { api, getToken } from '../../api'
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
      <div data-tour="usage-tiles" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map(({ label, value, Icon, note }, i) => (
          <motion.div key={label} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }} className="card p-5">
            <div className="flex items-center justify-between text-muted"><span className="text-sm font-medium">{label}</span><Icon size={18} /></div>
            <p className="mt-2 text-4xl font-semibold tracking-tighter"><CountUp value={value} /></p>
            {note && <p className="mt-1 text-xs text-muted">{note}</p>}
          </motion.div>
        ))}
      </div>

      <div className="mt-6">
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

      </div>
      <History />
    </>
  )
}

const FILTERS = [['all', 'All'], ['answered', 'Answered'], ['needs_info', 'Asked for details'], ['no_knowledge', 'Not in documents']]
const PER_PAGE = 15

function History() {
  const [q, setQ] = useState('')
  const [term, setTerm] = useState('')
  const [outcome, setOutcome] = useState('all')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => { const t = setTimeout(() => { setTerm(q.trim()); setPage(1) }, 300); return () => clearTimeout(t) }, [q])
  const load = useCallback(() => {
    const qs = new URLSearchParams({ page, per_page: PER_PAGE, q: term, outcome })
    api(`/usage/history?${qs}`).then((d) => { setData(d); setFailed(false); setOpen(null) }).catch(() => setFailed(true))
  }, [page, term, outcome])
  useEffect(() => { load() }, [load])

  async function exportCsv() {
    try {
      const qs = new URLSearchParams({ q: term, outcome })
      const res = await fetch(`/api/usage/history.csv?${qs}`, { headers: { Authorization: `Bearer ${getToken()}` } })
      if (!res.ok) throw new Error()
      const url = URL.createObjectURL(await res.blob())
      const a = Object.assign(document.createElement('a'), { href: url, download: 'question-history.csv' })
      a.click(); URL.revokeObjectURL(url)
    } catch { toast.error('Could not download the history. Please try again.') }
  }

  const from = data ? (data.total ? (data.page - 1) * PER_PAGE + 1 : 0) : 0
  const to = data ? Math.min(data.page * PER_PAGE, data.total) : 0
  return (
    <section data-tour="history" className="card mt-6 p-5 sm:p-6" aria-labelledby="hist-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="hist-title" className="font-semibold tracking-tight">Question history</h2>
          <p className="mt-0.5 text-sm text-muted">Every question visitors have asked, with the answer they got.</p>
        </div>
        <button className="btn btn-ghost !py-2 text-sm" onClick={exportCsv} disabled={!data?.total}><DownloadSimple size={16} />Download CSV</button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="relative min-w-[14rem] flex-1">
          <span className="sr-only">Search questions and answers</span>
          <MagnifyingGlass size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
          <input className="input !pl-10" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search questions and answers" maxLength={200} />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by outcome">
          {FILTERS.map(([v, label]) => (
            <button key={v} onClick={() => { setOutcome(v); setPage(1) }} aria-pressed={outcome === v}
              className={`rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors ${outcome === v ? 'border-accent bg-accent-soft text-accent' : 'border-line hover:bg-surface-2'}`}>{label}</button>
          ))}
        </div>
      </div>

      {failed ? (
        <p role="alert" className="mt-6 rounded-xl bg-bad-soft px-4 py-3 text-sm font-medium text-bad">Could not load the history. <button className="underline" onClick={load}>Try again</button></p>
      ) : !data ? (
        <div className="mt-5 space-y-3"><div className="skeleton h-12" /><div className="skeleton h-12" /><div className="skeleton h-12" /></div>
      ) : data.total === 0 ? (
        <div className="grid place-items-center py-12 text-center"><ChatsCircle size={36} weight="duotone" className="text-muted" />
          <p className="mt-2 text-sm text-muted">{term || outcome !== 'all' ? 'No questions match this search.' : 'No questions yet. Try your assistant from the Assistant tab.'}</p></div>
      ) : (
        <>
          <ul className="mt-4 divide-y divide-line">
            {data.items.map((r) => {
              const o = OUTCOME[r.outcome] || OUTCOME.error
              const isOpen = open === r.id
              return (
                <li key={r.id}>
                  <button className="flex w-full items-start gap-3 py-3 text-left" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : r.id)}>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm leading-snug">{r.question}</p>
                      <p className="mt-0.5 text-xs text-muted">{new Date(r.at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</p>
                    </div>
                    <span className={`chip shrink-0 ${o.cls}`}>{o.text}</span>
                    <CaretDown size={16} className={`mt-0.5 shrink-0 text-muted transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                  </button>
                  {isOpen && (
                    <div className="mb-3 rounded-xl bg-surface-2 p-4 text-sm">
                      <p className="whitespace-pre-wrap leading-relaxed">{r.answer || 'No answer was recorded for this question (asked before history was kept).'}</p>
                      <p className="mt-3 text-xs text-muted">
                        {r.sources ? <>Sources: <span className="font-mono">{r.sources}</span> · </> : null}
                        {r.type ? <>{r.type.replace(/_/g, ' ')} · </> : null}{(r.latency_ms / 1000).toFixed(1)}s
                      </p>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
          <div className="mt-4 flex items-center justify-between gap-3 text-sm text-muted">
            <span>Showing {from}–{to} of {data.total}</span>
            <div className="flex items-center gap-2">
              <button className="btn btn-ghost !px-2.5 !py-2" onClick={() => setPage(page - 1)} disabled={page <= 1} aria-label="Previous page"><CaretLeft size={16} /></button>
              <span>Page {data.page} of {data.pages}</span>
              <button className="btn btn-ghost !px-2.5 !py-2" onClick={() => setPage(page + 1)} disabled={page >= data.pages} aria-label="Next page"><CaretRight size={16} /></button>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
