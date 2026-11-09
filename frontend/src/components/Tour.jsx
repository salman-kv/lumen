import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowLeft, ArrowRight, X } from '@phosphor-icons/react'

export const TOUR_KEY = 'lumen_tour_done'

/** One entry per stop. `target` is a CSS selector for the element to highlight; without it the card is centred. */
const STEPS = [
  { path: '/app', title: 'Welcome to Lumen', body: 'A two-minute tour of how it works: upload your PDFs, share your assistant, and see what visitors ask. You can skip at any time.' },
  { path: '/app', target: '[data-tour="nav"]', title: 'Four tabs, one flow', body: 'Overview tracks your setup. Knowledge holds your PDFs. Assistant is where you style and share the chat. Usage shows what visitors ask.' },
  { path: '/app', target: '[data-tour="checklist"]', title: 'Three steps to go live', body: 'Upload documents, personalise the assistant, then share the link. Each step ticks off by itself as you finish it.' },
  { path: '/app/knowledge', target: '[data-tour="upload"]', title: 'Add your policy PDFs', body: 'Drop up to 10 PDFs here (20 pages and 10 MB each). Each one is split into pages, searched, and scanned for rules like "GPA of at least 3.5". Other organizations never see them.' },
  { path: '/app/assistant', target: '[data-tour="share"]', title: 'Your public link', body: 'Anyone with this link can ask questions without an account. It never exposes your documents or this dashboard. Regenerate it any time to retire the old link.' },
  { path: '/app/assistant', target: '[data-tour="embed"]', title: 'Put it on your website', body: 'Copy the script for a floating chat bubble, or the iframe for an inline chat, and paste it into any page.' },
  { path: '/app/assistant', target: '[data-tour="appearance"]', title: 'Make it yours', body: 'Choose a name, colour and welcome message, and add up to 6 starter questions. We add more automatically from your documents.' },
  { path: '/app/assistant', target: '[data-tour="preview"]', title: 'Try it live', body: 'This is the real assistant, and it updates as you type. Ask it something. The "How I decided" panel under each answer shows every step it took.' },
  { path: '/app/usage', target: '[data-tour="usage-tiles"]', title: 'See how it is doing', body: 'How many questions were asked, answered, or not covered by your documents. "Unable to answer" points at what your PDFs are missing.' },
  { path: '/app/usage', target: '[data-tour="history"]', title: 'Every question, kept', body: 'Search the full history, filter by outcome, open a row to see the answer and its sources, or download everything as CSV.' },
  { path: '/app/usage', target: '[data-tour="open-assistant"]', title: 'You are all set', body: 'Open the assistant the way your visitors see it. You can replay this tour any time from "Take the tour".' },
]

const PAD = 8
const GAP = 14
const MARGIN = 12

const clip = (r, vw, vh) => {
  const top = Math.max(r.top, 0), left = Math.max(r.left, 0), bottom = Math.min(r.bottom, vh), right = Math.min(r.right, vw)
  return { top, left, bottom, right, width: Math.max(right - left, 0), height: Math.max(bottom - top, 0) }
}

function place(rect, card, vw, vh) {
  const fit = (v, size, max) => Math.min(Math.max(v, MARGIN), Math.max(max - size - MARGIN, MARGIN))
  if (!rect) return { top: fit((vh - card.h) / 2, card.h, vh), left: fit((vw - card.w) / 2, card.w, vw) }
  const below = vh - (rect.bottom + PAD) - MARGIN
  const above = rect.top - PAD - MARGIN
  const right = vw - (rect.right + PAD) - MARGIN
  const left = rect.left - PAD - MARGIN
  const midX = rect.left + rect.width / 2 - card.w / 2
  const midY = rect.top + rect.height / 2 - card.h / 2
  let top, x
  if (below >= card.h + GAP) { top = rect.bottom + PAD + GAP; x = midX }
  else if (above >= card.h + GAP) { top = rect.top - PAD - GAP - card.h; x = midX }
  else if (right >= card.w + GAP) { x = rect.right + PAD + GAP; top = midY }
  else if (left >= card.w + GAP) { x = rect.left - PAD - GAP - card.w; top = midY }
  else { top = vh - card.h - MARGIN; x = (vw - card.w) / 2 } // target fills the screen: sit over its lower edge
  return { top: fit(top, card.h, vh), left: fit(x, card.w, vw) }
}

export default function Tour({ open, onClose }) {
  const nav = useNavigate()
  const reduce = useReducedMotion()
  const [i, setI] = useState(0)
  const [rect, setRect] = useState(null)
  const [ready, setReady] = useState(false)
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight })
  const [size, setSize] = useState({ w: 340, h: 230 })
  const cardRef = useRef(null)
  const nextRef = useRef(null)
  const elRef = useRef(null)
  const step = STEPS[i]
  const last = i === STEPS.length - 1
  const small = vp.w < 640

  const finish = useCallback(() => {
    try { localStorage.setItem(TOUR_KEY, '1') } catch { /* private mode: it just shows again next time */ }
    onClose()
  }, [onClose])
  const go = useCallback((d) => setI((n) => Math.min(Math.max(n + d, 0), STEPS.length - 1)), [])

  useEffect(() => { if (open) setI(0) }, [open])

  const measure = useCallback(() => {
    const el = elRef.current
    if (!el || !el.isConnected) return
    setRect(el.getBoundingClientRect())
    setVp({ w: window.innerWidth, h: window.innerHeight })
  }, [])

  // Go to the step's page, wait for its element to exist, scroll it into view, then highlight it.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    let timer
    setReady(false)
    elRef.current = null
    if (window.location.pathname.replace(/\/$/, '') !== step.path) nav(step.path)
    const started = Date.now()
    const find = () => {
      if (cancelled) return
      if (!step.target) { setRect(null); setReady(true); return }
      const onPage = window.location.pathname.replace(/\/$/, '') === step.path
      const el = onPage ? document.querySelector(step.target) : null
      if (el) {
        elRef.current = el
        el.scrollIntoView({ block: window.innerWidth < 640 ? 'start' : 'center', behavior: reduce ? 'auto' : 'smooth' })
        timer = setTimeout(() => { if (!cancelled) { measure(); setReady(true) } }, reduce ? 60 : 480)
      } else if (Date.now() - started < 2500) timer = setTimeout(find, 100)
      else { setRect(null); setReady(true) } // element not on this screen size: show the card centred
    }
    find()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [open, i]) // eslint-disable-line react-hooks/exhaustive-deps

  // keep the highlight on the element while the page scrolls or resizes
  useEffect(() => {
    if (!open) return
    let raf = 0
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(measure) }
    window.addEventListener('resize', on)
    window.addEventListener('scroll', on, true)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', on); window.removeEventListener('scroll', on, true) }
  }, [open, measure])

  useEffect(() => {
    if (!open) return
    const key = (e) => {
      if (e.key === 'Escape') finish()
      else if (e.key === 'ArrowRight') last ? finish() : go(1)
      else if (e.key === 'ArrowLeft') go(-1)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [open, last, go, finish])

  useLayoutEffect(() => {
    if (!open || !cardRef.current) return
    setSize({ w: cardRef.current.offsetWidth, h: cardRef.current.offsetHeight })
  }, [open, i, ready, small])
  useEffect(() => { if (open && ready) nextRef.current?.focus({ preventScroll: true }) }, [open, ready, i])

  if (!open) return null
  const view = rect && ready ? clip(rect, vp.w, vp.h) : null
  const pos = small ? null : place(view, size, vp.w, vp.h)
  const spring = reduce ? { duration: 0 } : { type: 'spring', stiffness: 260, damping: 30 }

  return (
    <div className="fixed inset-0 z-[100]" role="presentation">
      {/* a transparent layer stops clicks reaching the page while the tour is open */}
      <div className="absolute inset-0" />
      {view ? (
        <motion.div aria-hidden className="pointer-events-none fixed rounded-2xl"
          style={{ boxShadow: '0 0 0 2px var(--accent), 0 0 24px 2px color-mix(in srgb, var(--accent) 45%, transparent), 0 0 0 9999px rgba(8, 12, 10, 0.64)' }} initial={false}
          animate={{ top: view.top - PAD, left: view.left - PAD, width: view.width + PAD * 2, height: view.height + PAD * 2 }} transition={spring} />
      ) : (
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-[rgba(8,12,10,0.64)]" />
      )}

      {ready && (
          <motion.div key={i} ref={cardRef} role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-body"
            className={`fixed rounded-2xl border border-line bg-surface p-5 shadow-card ${small ? 'inset-x-3 bottom-3' : 'w-[340px]'}`}
            style={small ? undefined : { top: pos.top, left: pos.left }}
            initial={reduce ? false : { opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}>
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-accent">Step {i + 1} of {STEPS.length}</p>
              <button onClick={finish} aria-label="Skip tour" className="-m-1 rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-ink"><X size={16} /></button>
            </div>
            <h2 id="tour-title" className="mt-2 text-lg font-semibold tracking-tight">{step.title}</h2>
            <p id="tour-body" className="mt-1.5 text-sm leading-relaxed text-muted">{step.body}</p>
            <div className="mt-4 flex items-center gap-1.5" aria-hidden>
              {STEPS.map((_, n) => <span key={n} className={`h-1.5 rounded-full transition-all ${n === i ? 'w-5 bg-accent' : 'w-1.5 bg-line'}`} />)}
            </div>
            <div className="mt-5 flex items-center justify-between gap-2">
              <button onClick={finish} className="text-sm font-semibold text-muted hover:text-ink">Skip tour</button>
              <div className="flex gap-2">
                {i > 0 && <button onClick={() => go(-1)} className="btn btn-ghost !px-3 !py-2 text-sm" aria-label="Previous step"><ArrowLeft size={15} />Back</button>}
                <button ref={nextRef} onClick={() => (last ? finish() : go(1))} className="btn btn-primary !py-2 text-sm">
                  {i === 0 ? 'Start tour' : last ? 'Finish' : 'Next'} {!last && <ArrowRight size={15} weight="bold" />}
                </button>
              </div>
            </div>
          </motion.div>
      )}
    </div>
  )
}
