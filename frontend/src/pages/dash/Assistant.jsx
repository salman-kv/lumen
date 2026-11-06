import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import { Link as LinkIcon, ArrowSquareOut, ArrowsClockwise, FloppyDisk, CircleNotch, Warning, Code, Browser } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { api } from '../../api'
import { useData, PageHeader } from '../Dashboard'
import { useAuth } from '../../auth'
import { CopyButton, Modal } from '../../components/ui'
import ChatPanel from '../../components/ChatPanel'

const SWATCHES = ['#0b8f6e', '#2563eb', '#e11d48', '#ea580c', '#7c3aed', '#0f172a']

function CodeBlock({ code, label }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-[#0c1210]">
      <div className="flex items-center justify-between border-b border-white/10 px-3.5 py-2">
        <span className="text-xs font-medium text-white/60">{label}</span>
        <CopyButton text={code} className="!border-white/15 !bg-white/5 !text-white/85 hover:!bg-white/10" />
      </div>
      <pre className="scroll-thin overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-[#cfe9df]"><code>{code}</code></pre>
    </div>
  )
}

export default function Assistant() {
  const { org } = useAuth()
  const { assistant, setAssistant, loadUsage } = useData()
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [embedTab, setEmbedTab] = useState('script')
  const [confirm, setConfirm] = useState(false)
  const [rotating, setRotating] = useState(false)
  const nav = useNavigate()

  useEffect(() => {
    if (assistant && !form) setForm({ assistant_name: assistant.assistant_name, brand_color: assistant.brand_color, welcome_message: assistant.welcome_message, suggestions: [...assistant.suggestions, '', '', '', ''].slice(0, 3) })
  }, [assistant]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => loadUsage(), [loadUsage])

  if (!assistant || !form) return <><PageHeader title="Assistant" /><div className="grid gap-5 lg:grid-cols-2"><div className="skeleton h-96" /><div className="skeleton h-96" /></div></>

  const dirty = form.assistant_name !== assistant.assistant_name || form.brand_color !== assistant.brand_color || form.welcome_message !== assistant.welcome_message
    || form.suggestions.filter(Boolean).join('|') !== assistant.suggestions.join('|')
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const markEmbedded = () => { try { localStorage.setItem(`kda_embed_${org.id}`, '1') } catch { /* ignore */ } }

  async function save() {
    if (!form.assistant_name.trim()) return toast.error('Give your assistant a name.')
    setSaving(true)
    try {
      const a = await api('/assistant', { method: 'PATCH', json: { ...form, suggestions: form.suggestions.filter((s) => s.trim()) } })
      setAssistant(a); toast.success('Assistant updated')
    } catch (e) { toast.error(e.message) } finally { setSaving(false) }
  }
  async function regenerate() {
    setRotating(true)
    try { const a = await api('/assistant/regenerate', { method: 'POST' }); setAssistant(a); setConfirm(false); toast.success('New link created. The old link no longer works.') }
    catch (e) { toast.error(e.message) } finally { setRotating(false) }
  }

  const embed = embedTab === 'script' ? assistant.embed_script : assistant.embed_iframe
  return (
    <>
      <PageHeader title="Assistant">Customize how your assistant looks, then share the link or embed it. The preview on the right is the real assistant: it updates as you type, and you can chat with it. Click Save to publish your changes.</PageHeader>
      <div className="grid items-start gap-6 xl:grid-cols-[1fr_24rem]">
        <div className="min-w-0 space-y-6">
          <section className="card p-5 sm:p-6">
            <h2 className="font-semibold tracking-tight">Public link</h2>
            <p className="mt-1 text-sm text-muted">Anyone with this link can ask questions. It never exposes your documents or dashboard.</p>
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-line bg-surface-2 p-1.5 pl-3.5">
              <LinkIcon size={16} className="shrink-0 text-muted" />
              <code className="min-w-0 flex-1 truncate font-mono text-[13px]" title={assistant.url}>{assistant.url}</code>
              <CopyButton text={assistant.url} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <a href={assistant.url} target="_blank" rel="noreferrer" className="btn btn-ghost !py-2 !text-[13px]"><ArrowSquareOut size={15} />Open assistant</a>
              <a href={`/demo.html?token=${assistant.token}`} target="_blank" rel="noreferrer" onClick={markEmbedded} className="btn btn-ghost !py-2 !text-[13px]"><Browser size={15} />Open demo page</a>
              <button className="btn btn-danger !py-2 !text-[13px]" onClick={() => setConfirm(true)}><ArrowsClockwise size={15} />Regenerate link</button>
            </div>
          </section>

          <section className="card p-5 sm:p-6">
            <div className="flex items-center gap-2"><Code size={20} className="text-accent" /><h2 className="font-semibold tracking-tight">Embed on your website</h2></div>
            <div role="tablist" className="mt-4 inline-flex rounded-xl bg-surface-2 p-1">
              {[['script', 'Chat bubble'], ['iframe', 'Inline panel']].map(([k, l]) => (
                <button key={k} role="tab" aria-selected={embedTab === k} onClick={() => setEmbedTab(k)} className={`relative rounded-lg px-3.5 py-1.5 text-sm font-semibold ${embedTab === k ? 'text-ink' : 'text-muted'}`}>
                  {embedTab === k && <motion.span layoutId="embed-tab" className="absolute inset-0 rounded-lg bg-surface shadow-sm" />}<span className="relative">{l}</span>
                </button>
              ))}
            </div>
            <p className="mt-3 text-sm text-muted">{embedTab === 'script' ? 'Adds a floating button that opens the assistant. Paste before the closing </body> tag.' : 'Places the assistant directly inside a page. Paste where it should appear.'}</p>
            <div className="mt-3" onCopy={markEmbedded}><CodeBlock code={embed} label={embedTab === 'script' ? 'HTML (script)' : 'HTML (iframe)'} /></div>
          </section>

          <section className="card p-5 sm:p-6">
            <h2 className="font-semibold tracking-tight">Appearance and greeting</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div><label className="label" htmlFor="aname">Assistant name</label><input id="aname" className="input" maxLength={80} value={form.assistant_name} onChange={set('assistant_name')} /></div>
              <div>
                <label className="label" htmlFor="acolor">Brand color</label>
                <div className="flex items-center gap-2">
                  {SWATCHES.map((c) => (
                    <button key={c} onClick={() => setForm({ ...form, brand_color: c })} aria-label={`Use color ${c}`} aria-pressed={form.brand_color.toLowerCase() === c}
                      className="size-8 rounded-full border-2 transition-transform hover:scale-110" style={{ background: c, borderColor: form.brand_color.toLowerCase() === c ? 'var(--ink)' : 'transparent' }} />
                  ))}
                  <input id="acolor" type="color" value={form.brand_color} onChange={set('brand_color')} className="size-8 cursor-pointer rounded-full border border-line bg-transparent p-0" aria-label="Pick a custom color" />
                </div>
              </div>
            </div>
            <div className="mt-4"><label className="label" htmlFor="welcome">Welcome message</label><textarea id="welcome" rows={2} maxLength={300} className="input resize-none" value={form.welcome_message} onChange={set('welcome_message')} /></div>
            <div className="mt-4">
              <p className="label">Suggested questions <span className="font-normal text-muted">(optional, up to 3)</span></p>
              <div className="space-y-2">
                {form.suggestions.map((s, i) => (
                  <input key={i} aria-label={`Suggested question ${i + 1}`} className="input" maxLength={140} value={s} placeholder={['Am I eligible for...?', 'How do I apply?', 'What is the policy on...?'][i]}
                    onChange={(e) => setForm({ ...form, suggestions: form.suggestions.map((x, j) => (j === i ? e.target.value : x)) })} />
                ))}
              </div>
            </div>
            <div className="mt-5 flex items-center gap-3">
              <button className="btn btn-primary" onClick={save} disabled={saving || !dirty}>{saving ? <CircleNotch size={16} className="animate-spin" /> : <FloppyDisk size={16} />}Save changes</button>
              <AnimatePresence>{dirty && <motion.span initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="text-sm text-muted">Unsaved changes</motion.span>}</AnimatePresence>
            </div>
          </section>
        </div>

        <aside className="min-w-0 xl:sticky xl:top-8">
          <p className="mb-2 text-sm font-semibold">Live preview <span className="font-normal text-muted">{dirty ? "(unsaved changes)" : "(what visitors see)"}</span></p>
          <div className="h-[34rem] sm:h-[38rem]"><ChatPanel key={assistant.token} token={assistant.token} className="h-full" preview={{ name: form.assistant_name || assistant.assistant_name, color: form.brand_color, welcome: form.welcome_message, suggestions: form.suggestions.filter(Boolean) }} /></div>
          <button onClick={() => nav('/app/usage')} className="mt-3 text-sm font-semibold text-accent hover:underline">See what visitors asked</button>
        </aside>
      </div>

      <Modal open={confirm} onClose={() => !rotating && setConfirm(false)} title="Regenerate the assistant link?">
        <p className="flex gap-2.5 rounded-xl bg-warn-soft p-3 text-sm leading-relaxed text-warn"><Warning size={18} weight="fill" className="mt-0.5 shrink-0" />The current link and any embed code using it will stop working immediately. You will need to update your website.</p>
        <div className="mt-6 flex justify-end gap-2">
          <button className="btn btn-ghost" onClick={() => setConfirm(false)} disabled={rotating}>Keep current link</button>
          <button className="btn btn-primary" onClick={regenerate} disabled={rotating}>{rotating && <CircleNotch size={16} className="animate-spin" />}Regenerate</button>
        </div>
      </Modal>
    </>
  )
}
