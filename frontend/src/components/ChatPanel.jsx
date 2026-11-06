import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  PaperPlaneTilt, FilePdf, CaretDown, ThumbsUp, ThumbsDown, CheckCircle, XCircle, Question,
  ArrowCounterClockwise, WarningCircle, Sparkle,
} from '@phosphor-icons/react'
import { api, askStream } from '../api'
import PipelineViz from './PipelineViz'
import { readableOn } from './ui'

const VERDICT = {
  eligible: { text: 'Eligible', Icon: CheckCircle, cls: 'bg-accent-soft text-accent' },
  not_eligible: { text: 'Not eligible', Icon: XCircle, cls: 'bg-bad-soft text-bad' },
  need_info: { text: 'More information needed', Icon: Question, cls: 'bg-warn-soft text-warn' },
}

function Typing() {
  return (
    <span className="inline-flex items-end gap-1 py-1" aria-label="Assistant is typing">
      {[0, 1, 2].map((i) => (
        <motion.span key={i} className="size-1.5 rounded-full bg-muted" animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }} />
      ))}
    </span>
  )
}

function Sources({ refs }) {
  const [open, setOpen] = useState(null)
  if (!refs?.length) return null
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">Sources</p>
      <div className="flex flex-wrap gap-1.5">
        {refs.map((r, i) => (
          <button key={i} onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}
            className={`inline-flex max-w-full items-center gap-1.5 rounded-lg border px-2 py-1 text-xs font-medium transition-colors ${open === i ? 'border-accent bg-accent-soft text-accent' : 'border-line bg-surface hover:bg-surface-2'}`}>
            <FilePdf size={14} weight="duotone" className="shrink-0" />
            <span className="truncate">{r.document}</span>
            <span className="shrink-0 rounded-md bg-surface-2 px-1.5 font-mono text-[11px] text-muted">p.{r.page}</span>
          </button>
        ))}
      </div>
      <AnimatePresence initial={false}>
        {open !== null && (
          <motion.blockquote key={open} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="mt-2 overflow-hidden rounded-xl border-l-2 border-accent bg-surface-2 text-[13px] leading-relaxed text-muted">
            <div className="p-3">
              <span className="mb-1 block font-semibold text-ink">{refs[open].document}, page {refs[open].page}</span>
              {refs[open].snippet}
            </div>
          </motion.blockquote>
        )}
      </AnimatePresence>
    </div>
  )
}

function BotMessage({ m, onRetry }) {
  const [show, setShow] = useState(true)
  const [vote, setVote] = useState(null)
  const wasPending = useRef(m.pending)
  useEffect(() => { if (wasPending.current && !m.pending) { setShow(false); wasPending.current = false } }, [m.pending])
  const v = VERDICT[m.final?.decisions?.verdict]
  const hasSteps = m.steps?.length > 0
  return (
    <div className="flex max-w-[92%] flex-col items-start gap-2">
      <div className={`rounded-2xl rounded-tl-md border px-4 py-3 text-[15px] leading-relaxed ${m.error ? 'border-bad/40 bg-bad-soft text-bad' : 'border-line bg-surface'}`}>
        {m.error && <WarningCircle size={18} weight="bold" className="mr-1.5 inline -mt-0.5" />}
        {v && !m.pending && (
          <motion.span initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 300, damping: 18 }}
            className={`chip mb-2 mr-2 ${v.cls}`}><v.Icon size={14} weight="fill" />{v.text}</motion.span>
        )}
        {m.text ? <span className="whitespace-pre-wrap">{m.text}</span> : !m.error && <Typing />}
        {m.pending && m.text && <span className="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 animate-pulse bg-ink" />}
        {m.final?.status === 'no_knowledge' && !m.pending && (
          <span className="mt-2 flex items-center gap-1.5 text-xs text-muted"><Sparkle size={13} />Not found in the knowledge base, so no answer was guessed.</span>
        )}
        {!m.pending && m.final && <Sources refs={m.final.references} />}
        {m.error && onRetry && (
          <button onClick={onRetry} className="mt-2 flex items-center gap-1.5 text-sm font-semibold underline underline-offset-2"><ArrowCounterClockwise size={14} />Try again</button>
        )}
      </div>
      {hasSteps && (
        <div className="w-full">
          <button onClick={() => setShow(!show)} aria-expanded={show}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-muted transition-colors hover:bg-surface-2 hover:text-ink">
            How I decided
            <CaretDown size={12} weight="bold" className={`transition-transform ${show ? 'rotate-180' : ''}`} />
            {m.final && <span className="font-mono font-normal">{(m.final.latency_ms / 1000).toFixed(1)}s</span>}
          </button>
          <AnimatePresence initial={false}>
            {show && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                <div className="mt-1 rounded-2xl border border-line bg-surface p-4">
                  <PipelineViz steps={m.steps} decisions={m.final?.decisions} compact />
                  {m.final?.degraded && <p className="mt-3 text-xs text-warn">The language model was unavailable, so a template answer was used. Decisions and sources are unaffected.</p>}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
      {!m.pending && m.final && (
        <div className="flex gap-1 pl-1 text-muted">
          {[['up', ThumbsUp], ['down', ThumbsDown]].map(([k, I]) => (
            <button key={k} onClick={() => setVote(vote === k ? null : k)} aria-label={k === 'up' ? 'Helpful' : 'Not helpful'} aria-pressed={vote === k}
              className={`rounded-lg p-1.5 transition-colors hover:bg-surface-2 ${vote === k ? 'text-accent' : ''}`}><I size={15} weight={vote === k ? 'fill' : 'regular'} /></button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatPanel({ token, embedded = false, className = '' }) {
  const reduce = useReducedMotion()
  const [cfg, setCfg] = useState(null)
  const [cfgError, setCfgError] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)
  const abortRef = useRef(null)
  const lastQ = useRef('')

  useEffect(() => {
    setCfg(null); setCfgError(null); setMsgs([])
    api(`/public/assistant/${encodeURIComponent(token)}`, { auth: false }).then(setCfg).catch((e) => setCfgError(e.message))
    return () => abortRef.current?.abort()
  }, [token])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'end' }) }, [msgs, reduce])

  const patchLast = (fn) => setMsgs((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)))

  async function send(q) {
    const question = (q ?? input).trim()
    if (!question || busy) return
    // Answering a "more information needed" reply: send the earlier question along so the new facts combine with it.
    const prevBot = msgs[msgs.length - 1]
    const context = prevBot?.final?.status === 'needs_info' ? msgs[msgs.length - 2]?.text || '' : ''
    lastQ.current = question
    setInput(''); setBusy(true)
    setMsgs((ms) => [...ms, { role: 'user', text: question }, { role: 'bot', text: '', steps: [], pending: true }])
    abortRef.current = new AbortController()
    try {
      await askStream(token, question, (ev) => {
        if (ev.type === 'step') patchLast((m) => {
          const rest = m.steps.filter((s) => s.id !== ev.id)
          const order = ['retrieve', 'classify', 'choose', 'understand', 'decide', 'combine', 'answer']
          return { ...m, steps: [...rest, ev].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id)) }
        })
        else if (ev.type === 'token') patchLast((m) => ({ ...m, text: m.text + ev.text }))
        else if (ev.type === 'replace') patchLast((m) => ({ ...m, text: ev.text }))
        else if (ev.type === 'final') patchLast((m) => ({ ...m, pending: false, final: ev.data, text: m.text || ev.data.answer }))
        else if (ev.type === 'error') patchLast((m) => ({ ...m, pending: false, error: true, text: ev.message }))
      }, abortRef.current.signal, context)
      patchLast((m) => (m.pending ? { ...m, pending: false, error: true, text: m.text || 'The answer was interrupted. Please try again.' } : m))
    } catch (e) {
      patchLast((m) => ({ ...m, pending: false, error: true, text: e.message }))
    } finally { setBusy(false) }
  }

  if (cfgError) {
    return (
      <div className={`grid place-items-center p-8 text-center ${className}`}>
        <div className="max-w-xs">
          <span className="mx-auto mb-4 grid size-12 place-items-center rounded-2xl bg-bad-soft text-bad"><WarningCircle size={26} /></span>
          <h2 className="text-lg font-semibold tracking-tight">This assistant link isn't working</h2>
          <p className="mt-1.5 text-sm text-muted">{cfgError}</p>
        </div>
      </div>
    )
  }
  if (!cfg) {
    return (
      <div className={`flex flex-col gap-4 p-5 ${className}`} aria-busy="true">
        <div className="skeleton h-14 w-full" /><div className="skeleton h-20 w-4/5" /><div className="skeleton ml-auto h-10 w-1/2" />
      </div>
    )
  }

  const brand = cfg.color
  const brandInk = readableOn(brand)
  return (
    <section className={`flex min-h-0 flex-col bg-bg ${embedded ? '' : 'overflow-hidden rounded-[20px] border border-line shadow-card'} ${className}`}
      style={{ '--brand': brand, '--brand-ink': brandInk }}>
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3">
        <span className="grid size-10 place-items-center rounded-xl text-base font-bold" style={{ background: brand, color: brandInk }}>{cfg.name.slice(0, 1).toUpperCase()}</span>
        <div className="min-w-0">
          <h1 className="truncate text-[15px] font-semibold leading-tight tracking-tight">{cfg.name}</h1>
          <p className="truncate text-xs text-muted">Answers come only from {cfg.org}'s documents</p>
        </div>
      </header>

      <div className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5" aria-live="polite">
        <motion.div initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="max-w-[88%] rounded-2xl rounded-tl-md border border-line bg-surface px-4 py-3 text-[15px] leading-relaxed">
          {cfg.welcome}
        </motion.div>
        {msgs.length === 0 && cfg.suggestions?.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {cfg.suggestions.map((s, i) => (
              <motion.button key={s} initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.08 }}
                onClick={() => send(s)} className="rounded-xl border border-line bg-surface px-3 py-2 text-left text-[13px] font-medium transition-colors hover:border-[color:var(--brand)] hover:bg-surface-2">
                {s}
              </motion.button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => m.role === 'user' ? (
          <motion.div key={i} initial={reduce ? false : { opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            className="ml-auto max-w-[85%] rounded-2xl rounded-tr-md px-4 py-2.5 text-[15px] leading-relaxed" style={{ background: brand, color: brandInk }}>{m.text}</motion.div>
        ) : (
          <motion.div key={i} initial={reduce ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <BotMessage m={m} onRetry={!busy && i === msgs.length - 1 && m.error ? () => { setMsgs((x) => x.slice(0, -2)); send(lastQ.current) } : null} />
          </motion.div>
        ))}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send() }} className="border-t border-line bg-surface p-3">
        <div className="flex items-end gap-2">
          <label htmlFor="ask" className="sr-only">Ask a question</label>
          <input id="ask" value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000} autoComplete="off"
            placeholder="Ask a question about our policies" className="input !rounded-xl" />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Send question"
            className="btn !px-3.5 !py-3" style={{ background: brand, color: brandInk }}>
            <PaperPlaneTilt size={18} weight="fill" />
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-muted">AI can make mistakes. Check the cited pages for anything important.</p>
      </form>
    </section>
  )
}
