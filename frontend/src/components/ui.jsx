import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence, useInView, useReducedMotion, animate } from 'motion/react'
import { Check, Copy, Moon, Sun, X } from '@phosphor-icons/react'
import { toast } from 'sonner'

export function Logo({ size = 28, text = true }) {
  return (
    <span className="inline-flex items-center gap-2.5 font-semibold tracking-tight">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="9" fill="var(--accent)" />
        <path d="M9 21.5V10.5h2.4v8.9H17V21.5H9Z" fill="var(--accent-ink)" />
        <circle cx="21.5" cy="12" r="2.3" fill="var(--accent-ink)" />
        <rect x="19.9" y="16" width="3.2" height="5.5" rx="1.6" fill="var(--accent-ink)" />
      </svg>
      {text && <span className="text-[1.05rem]">Lumen</span>}
    </span>
  )
}

export function ThemeToggle({ className = '' }) {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')
  const flip = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('kda_theme', next) } catch { /* ignore */ }
    setTheme(next)
  }
  return (
    <button onClick={flip} className={`btn btn-ghost !px-2.5 ${className}`} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={theme} initial={{ rotate: -60, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 60, opacity: 0 }} transition={{ duration: 0.18 }}>
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </motion.span>
      </AnimatePresence>
    </button>
  )
}

export function CopyButton({ text, label = 'Copy', className = '' }) {
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select()
      try { document.execCommand('copy') } catch { toast.error('Copy failed. Select the text and copy it manually.'); ta.remove(); return }
      ta.remove()
    }
    setDone(true); toast.success('Copied to clipboard'); setTimeout(() => setDone(false), 1600)
  }
  return (
    <button onClick={copy} className={`btn btn-ghost !py-1.5 !text-[13px] ${className}`}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={done ? 'd' : 'c'} initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.6, opacity: 0 }} className="inline-flex">
          {done ? <Check size={15} weight="bold" className="text-accent" /> : <Copy size={15} />}
        </motion.span>
      </AnimatePresence>
      {done ? 'Copied' : label}
    </button>
  )
}

export function CountUp({ value, className = '' }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!inView) return
    if (reduce) { setN(value); return }
    const c = animate(0, value, { duration: 0.9, ease: [0.16, 1, 0.3, 1], onUpdate: (v) => setN(Math.round(v)) })
    return () => c.stop()
  }, [inView, value, reduce])
  return <span ref={ref} className={className}>{n}</span>
}

export function Modal({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label={title} className="card relative w-full max-w-md p-6"
            initial={{ y: 24, scale: 0.97, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: 12, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}>
            <button onClick={onClose} className="absolute right-4 top-4 text-muted hover:text-ink" aria-label="Close"><X size={18} /></button>
            <h3 className="pr-8 text-lg font-semibold tracking-tight">{title}</h3>
            <div className="mt-3">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function Reveal({ children, delay = 0, className = '', y = 22 }) {
  const reduce = useReducedMotion()
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }} transition={{ duration: 0.65, delay, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </motion.div>
  )
}

export function readableOn(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '')
  if (!m) return '#ffffff'
  const n = parseInt(m[1], 16)
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.42 ? '#0b0f0d' : '#ffffff'
}
