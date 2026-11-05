import { useCallback, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  FilePdf, UploadSimple, Trash, ArrowsClockwise, CheckCircle, WarningCircle, CircleNotch, X, Download, ListChecks, CaretDown,
} from '@phosphor-icons/react'
import { toast } from 'sonner'
import { api, uploadFile, fmtBytes, getToken } from '../../api'
import { useData, PageHeader } from '../Dashboard'
import { Modal } from '../../components/ui'

const STAGES = ['Extracting text', 'Indexing passages', 'Reading policy rules']

function Ring({ value, max }) {
  const r = 34, c = 2 * Math.PI * r
  return (
    <div className="relative size-[88px] shrink-0">
      <svg viewBox="0 0 80 80" className="size-full -rotate-90" aria-hidden>
        <circle cx="40" cy="40" r={r} fill="none" stroke="var(--line)" strokeWidth="7" />
        <motion.circle cx="40" cy="40" r={r} fill="none" stroke="var(--accent)" strokeWidth="7" strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - Math.min(value / max, 1)) }} transition={{ type: 'spring', stiffness: 60, damping: 16 }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center"><span className="text-xl font-semibold tracking-tight">{value}<span className="text-sm text-muted">/{max}</span></span></div>
    </div>
  )
}

function StageBar({ stage }) {
  const idx = Math.max(0, STAGES.indexOf(stage))
  return (
    <div className="mt-2.5" aria-label={`Processing: ${stage}`}>
      <div className="flex gap-1.5">
        {STAGES.map((s, i) => (
          <div key={s} className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
            <motion.div className="h-full rounded-full bg-accent" initial={false} animate={{ width: i < idx ? '100%' : i === idx ? '60%' : '0%' }} />
            {i === idx && <span className="sr-only">{s}</span>}
          </div>
        ))}
      </div>
      <p className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-accent"><CircleNotch size={13} className="animate-spin" />{stage}...</p>
    </div>
  )
}

function DocRow({ d, onDelete, onReplace }) {
  const fileRef = useRef(null)
  const view = async () => {
    try {
      const res = await fetch(`/api/kb/documents/${d.id}/file`, { headers: { Authorization: `Bearer ${getToken()}` } })
      if (!res.ok) throw new Error()
      window.open(URL.createObjectURL(await res.blob()), '_blank')
    } catch { toast.error('Could not open this document.') }
  }
  return (
    <motion.li layout initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -30, height: 0, marginBottom: 0 }} transition={{ type: 'spring', stiffness: 260, damping: 28 }}
      className="card p-4 sm:p-5">
      <div className="flex items-start gap-4">
        <span className={`grid size-11 shrink-0 place-items-center rounded-xl ${d.status === 'failed' ? 'bg-bad-soft text-bad' : 'bg-accent-soft text-accent'}`}><FilePdf size={24} weight="duotone" /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold tracking-tight" title={d.filename}>{d.filename}</p>
          {d.status === 'ready' && (
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs text-muted">
              <span className="chip bg-surface-2">{d.pages} {d.pages === 1 ? 'page' : 'pages'}</span>
              <span className="chip bg-surface-2">{fmtBytes(d.size_bytes)}</span>
              <span className="chip bg-surface-2">{d.chunks} passages</span>
              {d.rules > 0 && <span className="chip bg-accent-soft text-accent">{d.rules} rules found</span>}
            </div>
          )}
          {d.status === 'processing' && <StageBar stage={d.stage} />}
          {d.status === 'failed' && <p className="mt-1.5 flex items-start gap-1.5 text-sm text-bad"><WarningCircle size={16} weight="bold" className="mt-0.5 shrink-0" />{d.error}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {d.status === 'ready' && <CheckCircle size={22} weight="fill" className="mr-1 hidden text-accent sm:block" aria-label="Ready" />}
          {d.status === 'ready' && <button onClick={view} className="rounded-xl p-2 text-muted hover:bg-surface-2 hover:text-ink" aria-label={`View ${d.filename}`}><Download size={18} /></button>}
          <button onClick={() => fileRef.current?.click()} disabled={d.status === 'processing'} className="rounded-xl p-2 text-muted hover:bg-surface-2 hover:text-ink disabled:opacity-40" aria-label={`Replace ${d.filename}`}><ArrowsClockwise size={18} /></button>
          <button onClick={() => onDelete(d)} className="rounded-xl p-2 text-muted hover:bg-bad-soft hover:text-bad" aria-label={`Delete ${d.filename}`}><Trash size={18} /></button>
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) onReplace(d, f) }} />
        </div>
      </div>
    </motion.li>
  )
}

function Rules() {
  const [rules, setRules] = useState(null)
  const [open, setOpen] = useState(false)
  const toggle = () => { setOpen(!open); if (!rules) api('/kb/rules').then((r) => setRules(r.rules)).catch((e) => toast.error(e.message)) }
  const groups = (rules || []).reduce((a, r) => { (a[r.benefit] ||= []).push(r); return a }, {})
  return (
    <div className="card mt-8">
      <button onClick={toggle} aria-expanded={open} className="flex w-full items-center gap-3 p-5 text-left">
        <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent"><ListChecks size={22} weight="duotone" /></span>
        <span className="flex-1"><span className="block font-semibold tracking-tight">What the assistant learned</span><span className="text-sm text-muted">Decision rules found in your policies, each linked to its page.</span></span>
        <CaretDown size={18} className={`text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="grid gap-4 border-t border-line p-5 sm:grid-cols-2">
              {!rules && <div className="skeleton h-24" />}
              {rules && !rules.length && <p className="text-sm text-muted sm:col-span-2">No rules detected yet. Policies with conditions such as "minimum GPA of 3.5" or "at least 6 months of service" are picked up automatically.</p>}
              {Object.entries(groups).map(([b, rs]) => (
                <div key={b} className="rounded-2xl bg-surface-2 p-4">
                  <h4 className="font-semibold tracking-tight">{b}</h4>
                  <ul className="mt-2.5 space-y-1.5 text-sm">
                    {rs.map((r) => (
                      <li key={r.id} className="flex items-baseline justify-between gap-3"><span>{r.label}: <span className="font-mono text-[13px] text-muted">{r.operator === 'is_true' ? 'required' : r.operator === 'is_false' ? 'must not apply' : `${r.operator} ${r.value}`}</span></span><span className="shrink-0 font-mono text-[11px] text-muted">p.{r.page}</span></li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function Knowledge() {
  const { docs, limits, loadDocs, loadAssistant } = useData()
  const [queue, setQueue] = useState([])
  const [over, setOver] = useState(false)
  const [del, setDel] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const inputRef = useRef(null)
  const count = docs?.length ?? 0

  const precheck = (f) => {
    if (!/\.pdf$/i.test(f.name)) return `"${f.name}" is not a PDF. Only .pdf files are supported.`
    if (f.size > limits.max_pdf_mb * 1048576) return `"${f.name}" is ${fmtBytes(f.size)}. The maximum size is ${limits.max_pdf_mb} MB per PDF.`
    return null
  }

  const upload = useCallback(async (files) => {
    for (const f of files) {
      const id = Math.random().toString(36).slice(2)
      const early = precheck(f)
      if (early) { toast.error(early); continue }
      setQueue((q) => [...q, { id, name: f.name, p: 0 }])
      try {
        await uploadFile('/kb/documents', f, (p) => setQueue((q) => q.map((x) => (x.id === id ? { ...x, p } : x))))
        await loadDocs()
      } catch (e) { toast.error(e.message, { duration: 7000 }) } finally { setQueue((q) => q.filter((x) => x.id !== id)) }
    }
    loadAssistant()
  }, [loadDocs, loadAssistant, limits]) // eslint-disable-line react-hooks/exhaustive-deps

  const replace = async (d, f) => {
    const early = precheck(f)
    if (early) return toast.error(early)
    const id = 'r' + d.id
    setQueue((q) => [...q, { id, name: `${d.filename} -> ${f.name}`, p: 0 }])
    try { await uploadFile(`/kb/documents/${d.id}`, f, (p) => setQueue((q) => q.map((x) => (x.id === id ? { ...x, p } : x))), 'PUT'); await loadDocs(); toast.success('Document replaced') }
    catch (e) { toast.error(e.message, { duration: 7000 }) } finally { setQueue((q) => q.filter((x) => x.id !== id)) }
  }

  const confirmDelete = async () => {
    setDeleting(true)
    try { await api(`/kb/documents/${del.id}`, { method: 'DELETE' }); toast.success(`Removed ${del.filename}`); setDel(null); await loadDocs() }
    catch (e) { toast.error(e.message) } finally { setDeleting(false) }
  }

  const full = count >= limits.max_docs
  return (
    <>
      <PageHeader title="Knowledge base">Everything your assistant knows comes from these PDFs. Other organizations can never see them.</PageHeader>

      <div className="grid gap-5 md:grid-cols-[1fr_auto]">
        <div onDragOver={(e) => { e.preventDefault(); !full && setOver(true) }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); if (!full) upload([...e.dataTransfer.files]); else toast.error(`Your knowledge base is full (${limits.max_docs} documents). Delete one first.`) }}
          className={`relative rounded-[20px] border-2 border-dashed p-8 text-center transition-colors sm:p-10 ${over ? 'border-accent bg-accent-soft' : 'border-line bg-surface'} ${full ? 'opacity-60' : ''}`}>
          <motion.span animate={over ? { y: -6, scale: 1.08 } : { y: 0, scale: 1 }} className="mx-auto grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent"><UploadSimple size={28} weight="duotone" /></motion.span>
          <h2 className="mt-4 text-lg font-semibold tracking-tight">{full ? 'Knowledge base is full' : 'Drop PDFs here'}</h2>
          <p className="mx-auto mt-1 max-w-[42ch] text-sm text-muted">Up to {limits.max_pages} pages and {limits.max_pdf_mb} MB each. Text-based PDFs work best.</p>
          <button className="btn btn-primary mt-5" disabled={full} onClick={() => inputRef.current?.click()}>Choose files</button>
          <input ref={inputRef} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => { upload([...e.target.files]); e.target.value = '' }} />
        </div>
        <div className="card flex items-center gap-5 p-5 md:flex-col md:justify-center md:px-8">
          <Ring value={count} max={limits.max_docs} />
          <div className="text-sm text-muted md:text-center"><p className="font-semibold text-ink">Documents used</p><p>{Math.max(limits.max_docs - count, 0)} slots left</p></div>
        </div>
      </div>

      <AnimatePresence>
        {queue.map((q) => (
          <motion.div key={q.id} layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }} className="card mt-4 flex items-center gap-4 p-4">
            <CircleNotch size={20} className="shrink-0 animate-spin text-accent" />
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{q.name}</p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line"><motion.div className="h-full rounded-full bg-accent" animate={{ width: `${Math.round(q.p * 100)}%` }} /></div></div>
            <span className="font-mono text-xs text-muted">{Math.round(q.p * 100)}%</span>
          </motion.div>
        ))}
      </AnimatePresence>

      <section className="mt-8" aria-label="Uploaded documents">
        {docs === null && <div className="space-y-3"><div className="skeleton h-24" /><div className="skeleton h-24" /></div>}
        {docs?.length === 0 && queue.length === 0 && (
          <div className="card grid place-items-center px-6 py-12 text-center"><FilePdf size={40} weight="duotone" className="text-muted" />
            <h3 className="mt-3 font-semibold">No documents yet</h3><p className="mt-1 max-w-[40ch] text-sm text-muted">Upload your first PDF and your assistant will be ready to answer questions about it.</p></div>
        )}
        <ul className="space-y-3"><AnimatePresence initial={false}>{docs?.map((d) => <DocRow key={d.id} d={d} onDelete={setDel} onReplace={replace} />)}</AnimatePresence></ul>
      </section>

      <Rules />

      <Modal open={!!del} onClose={() => !deleting && setDel(null)} title="Delete this document?">
        <p className="text-sm leading-relaxed text-muted"><span className="font-semibold text-ink">{del?.filename}</span> and everything learned from it will be removed. The assistant will stop using it right away.</p>
        <div className="mt-6 flex justify-end gap-2">
          <button className="btn btn-ghost" onClick={() => setDel(null)} disabled={deleting}>Cancel</button>
          <button className="btn btn-danger-solid" onClick={confirmDelete} disabled={deleting}>{deleting ? <CircleNotch size={16} className="animate-spin" /> : <X size={16} weight="bold" />}Delete</button>
        </div>
      </Modal>
    </>
  )
}
