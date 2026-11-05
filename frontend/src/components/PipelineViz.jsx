import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  MagnifyingGlass, Tag, GitBranch, Sparkle, ListChecks, GitMerge, ChatText,
  Check, X, Question, CircleNotch, Minus, WarningCircle,
} from '@phosphor-icons/react'

const STAGES = [
  { id: 'retrieve', label: 'Search documents', kind: 's1', Icon: MagnifyingGlass },
  { id: 'classify', label: 'Classify question', kind: 's1', Icon: Tag },
  { id: 'choose', label: 'Choose policy', kind: 's1', Icon: GitBranch },
  { id: 'understand', label: 'Understand facts', kind: 'llm', Icon: Sparkle },
  { id: 'decide', label: 'Check conditions', kind: 's1', Icon: ListChecks },
  { id: 'combine', label: 'Combine results', kind: 'app', Icon: GitMerge },
  { id: 'answer', label: 'Write answer', kind: 'llm', Icon: ChatText },
]

const KIND = {
  llm: { text: 'LLM', cls: 'bg-accent-soft text-accent border-transparent' },
  s1: { text: 'System 1', cls: 'bg-transparent text-ink border-line' },
  app: { text: 'App logic', cls: 'bg-surface-2 text-muted border-transparent' },
}

function Node({ status, Icon }) {
  const base = 'grid size-8 shrink-0 place-items-center rounded-xl border transition-colors'
  if (status === 'done') return <span className={`${base} border-transparent bg-accent text-accent-ink`}><Check size={16} weight="bold" /></span>
  if (status === 'running') return <span className={`${base} pulse-ring border-accent bg-accent-soft text-accent`}><CircleNotch size={16} weight="bold" className="animate-spin" /></span>
  if (status === 'error') return <span className={`${base} border-transparent bg-warn-soft text-warn`}><WarningCircle size={16} weight="bold" /></span>
  if (status === 'skipped') return <span className={`${base} border-dashed border-line text-muted`}><Minus size={14} /></span>
  return <span className={`${base} border-line text-muted`}><Icon size={15} /></span>
}

const RESULT = {
  pass: { Icon: Check, cls: 'bg-accent-soft text-accent', text: 'Met' },
  fail: { Icon: X, cls: 'bg-bad-soft text-bad', text: 'Not met' },
  unknown: { Icon: Question, cls: 'bg-warn-soft text-warn', text: 'Need info' },
}

function Lanes({ decisions, reduce }) {
  const rows = decisions?.booleans || []
  if (!rows.length) return null
  return (
    <div className="mt-2 ml-1 border-l-2 border-line pl-3">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">Run in parallel</p>
      <ul className="space-y-1.5">
        {rows.map((r, i) => {
          const R = RESULT[r.result]
          return (
            <motion.li key={r.field} initial={reduce ? false : { opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.08 * i, type: 'spring', stiffness: 220, damping: 22 }}
              className="flex items-center gap-2 rounded-xl bg-surface-2 px-2.5 py-1.5 text-[13px]">
              <span className={`grid size-5 shrink-0 place-items-center rounded-lg ${R.cls}`}><R.Icon size={12} weight="bold" /></span>
              <span className="min-w-0 flex-1 truncate" title={r.rule}>{r.rule}</span>
              <span className="shrink-0 font-mono text-[11px] text-muted">
                {r.actual !== null && r.actual !== undefined ? `you: ${String(r.actual)}` : 'not stated'}
              </span>
            </motion.li>
          )
        })}
      </ul>
      {decisions?.score && (
        <p className="mt-2 text-xs text-muted">
          Evidence support score <span className="font-mono font-semibold text-ink">{Math.round(decisions.score.support * 100)}%</span>
        </p>
      )}
    </div>
  )
}

export default function PipelineViz({ steps = [], decisions = null, compact = false }) {
  const reduce = useReducedMotion()
  const byId = Object.fromEntries(steps.map((s) => [s.id, s]))
  return (
    <ol className={`relative ${compact ? 'space-y-2.5' : 'space-y-3.5'}`} aria-label="How the answer was produced">
      {STAGES.map(({ id, label, kind, Icon }, i) => {
        const s = byId[id]
        const status = s?.status || 'pending'
        const k = KIND[kind]
        return (
          <li key={id} className="relative flex gap-3">
            {i < STAGES.length - 1 && <span aria-hidden className="absolute left-4 top-8 -bottom-3 w-px bg-line" />}
            <Node status={status} Icon={Icon} />
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className={`text-sm font-semibold ${status === 'pending' || status === 'skipped' ? 'text-muted' : 'text-ink'}`}>{label}</span>
                <span className={`chip border ${k.cls} !py-0 !text-[10px]`}>{k.text}</span>
                {s?.ms > 0 && status !== 'running' && <span className="font-mono text-[11px] text-muted">{s.ms} ms</span>}
              </div>
              <AnimatePresence initial={false}>
                {s?.detail && status !== 'pending' && (
                  <motion.p key={s.detail} initial={reduce ? false : { opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                    className="mt-0.5 text-[13px] leading-snug text-muted">{s.detail}</motion.p>
                )}
              </AnimatePresence>
              {id === 'decide' && status === 'done' && <Lanes decisions={decisions} reduce={reduce} />}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
