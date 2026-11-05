import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowRight, Brain, Lightning, GitMerge, Quotes, Lock, FilePdf, Code, Plugs, ShieldCheck } from '@phosphor-icons/react'
import { Logo, ThemeToggle, Reveal, CopyButton } from '../components/ui'
import PipelineViz from '../components/PipelineViz'
import { useAuth } from '../auth'

/* Scripted run of the REAL pipeline component, mirroring what the API returns for the scholarship example. */
const DEMO_Q = "I'm a second-year student with a 3.6 GPA and I already have a sports scholarship. Am I eligible for the Merit Scholarship?"
const DEMO_STEPS = [
  { id: 'retrieve', status: 'done', ms: 142, detail: '5 passages, best match 91%' },
  { id: 'classify', status: 'done', ms: 18, detail: 'eligibility (94%)' },
  { id: 'choose', status: 'done', ms: 9, detail: 'Merit Scholarship (88% match)' },
  { id: 'understand', status: 'done', ms: 3120, detail: 'Year of study=2, Cumulative GPA=3.6, Holds a Sports Scholarship=true' },
  { id: 'decide', status: 'done', ms: 2, detail: '3 checks in parallel: 2 met' },
  { id: 'combine', status: 'done', ms: 0, detail: 'not eligible' },
  { id: 'answer', status: 'done', ms: 4210, detail: 'ollama' },
]
const DEMO_DECISIONS = {
  score: { support: 0.91 },
  booleans: [
    { field: 'year', rule: 'Year of study: at least 2', actual: 2, result: 'pass' },
    { field: 'gpa', rule: 'Cumulative GPA: at least 3.5', actual: 3.6, result: 'pass' },
    { field: 'holds_sports_scholarship', rule: 'Holds a Sports Scholarship: must not apply', actual: true, result: 'fail' },
  ],
}

function HeroDemo() {
  const reduce = useReducedMotion()
  const [n, setN] = useState(reduce ? DEMO_STEPS.length : 0)
  useEffect(() => {
    if (reduce) return
    const t = setInterval(() => setN((x) => (x >= DEMO_STEPS.length + 3 ? 0 : x + 1)), 1100)
    return () => clearInterval(t)
  }, [reduce])
  const steps = DEMO_STEPS.slice(0, n).map((s, i) => (i === n - 1 && n <= DEMO_STEPS.length && n < DEMO_STEPS.length ? { ...s, status: 'running', detail: '' } : s))
  const finished = n >= DEMO_STEPS.length
  return (
    <div className="card relative overflow-hidden p-5 sm:p-6">
      <div className="ml-auto mb-4 max-w-[92%] rounded-2xl rounded-tr-md bg-accent px-4 py-2.5 text-sm leading-relaxed text-accent-ink">{DEMO_Q}</div>
      <PipelineViz steps={steps} decisions={finished ? DEMO_DECISIONS : null} compact />
      <motion.div animate={{ opacity: finished ? 1 : 0.0, y: finished ? 0 : 8 }} className="mt-4 rounded-2xl border border-line bg-surface-2 p-3.5 text-sm leading-relaxed">
        <span className="chip mb-1.5 bg-bad-soft text-bad">Not eligible</span>
        <p>You meet the year and GPA conditions, but the Merit Scholarship can't be combined with a Sports Scholarship (Scholarship_Rules.pdf, p.1).</p>
      </motion.div>
    </div>
  )
}

const code = (origin) => `<script src="${origin}/embed.js" data-token="ast_your_token" async></script>`

export default function Landing() {
  const { org } = useAuth()
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const reduce = useReducedMotion()
  return (
    <div className="min-h-[100dvh]">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-bg/85 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link to="/" aria-label="Lumen home"><Logo /></Link>
          <div className="hidden items-center gap-7 text-sm font-medium text-muted md:flex">
            <a href="#layers" className="hover:text-ink">How it works</a>
            <a href="#embed" className="hover:text-ink">Embed</a>
            <a href="#isolation" className="hover:text-ink">Security</a>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {org ? <Link to="/app" className="btn btn-primary">Dashboard</Link> : <>
              <Link to="/login" className="btn btn-ghost hidden sm:inline-flex">Sign in</Link>
              <Link to="/register" className="btn btn-primary">Start free</Link>
            </>}
          </div>
        </nav>
      </header>

      <main>
        {/* HERO */}
        <section className="relative overflow-hidden">
          <div aria-hidden className="bg-grid absolute inset-0 opacity-60" />
          <motion.div aria-hidden className="absolute -right-40 -top-40 size-[34rem] rounded-full bg-accent/15 blur-3xl"
            animate={reduce ? undefined : { x: [0, -40, 0], y: [0, 30, 0] }} transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }} />
          <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:pb-28 lg:pt-20">
            <div>
              <motion.h1 initial={reduce ? false : { opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="text-4xl font-semibold leading-[1.05] tracking-tighter sm:text-5xl lg:text-6xl">
                An assistant that reads your PDFs and <span className="text-accent">makes the call.</span>
              </motion.h1>
              <motion.p initial={reduce ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="mt-5 max-w-[46ch] text-lg leading-relaxed text-muted">
                Upload policies, share one link. Answers cite the page, and eligibility questions run through real decision checks.
              </motion.p>
              <motion.div initial={reduce ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.24, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="mt-8 flex flex-wrap items-center gap-3">
                <Link to={org ? '/app' : '/register'} className="btn btn-primary !px-5 !py-3 !text-base">Start free <ArrowRight size={18} weight="bold" /></Link>
                <a href="#layers" className="btn btn-ghost !px-5 !py-3 !text-base">See how it works</a>
              </motion.div>
            </div>
            <motion.div initial={reduce ? false : { opacity: 0, y: 32, rotate: 1.2 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ delay: 0.2, duration: 0.9, ease: [0.16, 1, 0.3, 1] }}>
              <HeroDemo />
            </motion.div>
          </div>
        </section>

        {/* LAYERS (bento: 4 cells, 3x2 grid, no empty cell) */}
        <section id="layers" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
          <Reveal>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Built on three layers</p>
            <h2 className="mt-3 max-w-[22ch] text-3xl font-semibold tracking-tighter sm:text-4xl lg:text-5xl">The LLM talks. Small models decide.</h2>
            <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted">Language models are great at reading and writing, and unreliable at rules. So each job goes to the right tool.</p>
          </Reveal>
          <div className="mt-12 grid gap-4 lg:grid-cols-3 lg:grid-rows-2">
            <Reveal className="lg:col-span-2">
              <div className="relative h-full overflow-hidden rounded-[20px] bg-accent p-7 text-accent-ink sm:p-9">
                <Brain size={30} weight="duotone" />
                <h3 className="mt-5 text-2xl font-semibold tracking-tight">Language model</h3>
                <p className="mt-2 max-w-[52ch] text-[15px] leading-relaxed opacity-90">Reads the question, pulls out the facts the visitor stated, and writes the final answer in plain English. It never gets to overrule a decision.</p>
                <div aria-hidden className="absolute -bottom-16 -right-10 size-56 rounded-full border-[28px] border-accent-ink/10" />
              </div>
            </Reveal>
            <Reveal delay={0.08} className="lg:row-span-2">
              <div className="card h-full p-7 sm:p-9">
                <Lightning size={30} weight="duotone" className="text-accent" />
                <h3 className="mt-5 text-2xl font-semibold tracking-tight">System 1 models</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-muted">Fast, local, deterministic. Each one makes a single specific decision, all at the same time.</p>
                <ul className="mt-6 space-y-3 text-sm">
                  {[['Classify', 'What kind of question is this?'], ['Choose', 'Which policy applies?'], ['Boolean', 'Is each condition met?'], ['Score', 'How well do the documents support it?']].map(([k, v]) => (
                    <li key={k} className="rounded-xl bg-surface-2 px-3.5 py-2.5"><span className="font-semibold">{k}</span><span className="block text-muted">{v}</span></li>
                  ))}
                </ul>
              </div>
            </Reveal>
            <Reveal delay={0.12}>
              <div className="card h-full bg-surface-2 p-7 sm:p-8">
                <GitMerge size={28} weight="duotone" className="text-accent" />
                <h3 className="mt-4 text-xl font-semibold tracking-tight">Application logic</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-muted">Combines every check into one verdict and asks for missing facts instead of guessing.</p>
              </div>
            </Reveal>
            <Reveal delay={0.16}>
              <div className="card h-full p-7 sm:p-8" style={{ backgroundImage: 'radial-gradient(var(--line) 1px, transparent 1px)', backgroundSize: '16px 16px' }}>
                <Quotes size={28} weight="duotone" className="text-accent" />
                <h3 className="mt-4 text-xl font-semibold tracking-tight">Grounded answers</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-muted">Every answer links to the document and page. If the PDFs don't say, the assistant says so.</p>
              </div>
            </Reveal>
          </div>
        </section>

        {/* EMBED */}
        <section id="embed" className="border-y border-line bg-surface-2/60">
          <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-28">
            <Reveal>
              <h2 className="max-w-[18ch] text-3xl font-semibold tracking-tighter sm:text-4xl lg:text-5xl">One line puts it on your site.</h2>
              <p className="mt-4 max-w-[52ch] text-lg leading-relaxed text-muted">Paste the script tag for a floating chat bubble, or use the iframe for a fixed panel. Visitors never need an account.</p>
              <ul className="mt-8 space-y-4">
                {[[Plugs, 'Works on any page', 'A single script, no build step.'], [Lock, 'Private by design', 'The link carries a random token, never your documents.'], [Code, 'Regenerate any time', 'Rotate the token and the old link stops working.']].map(([I, t, d]) => (
                  <li key={t} className="flex gap-3.5"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><I size={20} /></span><span><span className="block font-semibold">{t}</span><span className="text-sm text-muted">{d}</span></span></li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="overflow-hidden rounded-[20px] border border-line bg-[#0c1210] shadow-card">
                <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
                  <span className="font-mono text-xs text-white/55">your-site.html</span>
                  <CopyButton text={code(origin)} className="!border-white/15 !bg-white/5 !text-white/80 hover:!bg-white/10" />
                </div>
                <pre className="scroll-thin overflow-x-auto p-5 font-mono text-[13px] leading-relaxed text-[#cfe9df]"><code>{`<body>\n  <!-- your page -->\n\n  ${code(origin)}\n</body>`}</code></pre>
              </div>
            </Reveal>
          </div>
        </section>

        {/* ISOLATION */}
        <section id="isolation" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-20 sm:px-6 lg:py-28">
          <Reveal>
            <h2 className="max-w-[24ch] text-3xl font-semibold tracking-tighter sm:text-4xl lg:text-5xl">Every organization gets its own walls.</h2>
            <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-muted">Retrieval is scoped to the organization behind the link, at the database query. One tenant's documents can never answer another's questions.</p>
          </Reveal>
          <div className="mt-12 grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr]">
            {[['Northfield University', ['Scholarship_Rules.pdf', 'Admissions_FAQ.pdf', 'Fee_Policy.pdf']], ['Acme Corp', ['Leave_Policy.pdf', 'Remote_Work_Policy.pdf', 'Expense_Policy.pdf']]].map(([name, files], idx) => (
              <Fragment key={name}>
                {idx === 1 && (
                  <div key="wall" className="flex items-center justify-center md:flex-col" aria-hidden>
                    <div className="h-px w-full border-t-2 border-dashed border-line md:h-full md:w-px md:border-l-2 md:border-t-0" />
                    <span className="mx-3 grid size-11 shrink-0 place-items-center rounded-full border border-line bg-surface text-accent md:my-3 md:mx-0"><ShieldCheck size={22} weight="duotone" /></span>
                    <div className="h-px w-full border-t-2 border-dashed border-line md:h-full md:w-px md:border-l-2 md:border-t-0" />
                  </div>
                )}
                <Reveal key={name} delay={idx * 0.1}>
                  <div className="card h-full p-6">
                    <h3 className="text-lg font-semibold tracking-tight">{name}</h3>
                    <ul className="mt-4 space-y-2">
                      {files.map((f) => <li key={f} className="flex items-center gap-2.5 rounded-xl bg-surface-2 px-3 py-2.5 text-sm"><FilePdf size={18} weight="duotone" className="text-accent" />{f}</li>)}
                    </ul>
                  </div>
                </Reveal>
              </Fragment>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="px-4 pb-20 sm:px-6 lg:pb-28">
          <Reveal>
            <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[28px] bg-[#0c1210] px-6 py-16 text-center sm:px-12">
              <div aria-hidden className="absolute inset-0 opacity-40" style={{ backgroundImage: 'radial-gradient(circle at 20% 0%, rgb(47 199 158 / 0.35), transparent 45%)' }} />
              <h2 className="relative mx-auto max-w-[20ch] text-3xl font-semibold tracking-tighter text-white sm:text-5xl">Build your assistant in five minutes.</h2>
              <p className="relative mx-auto mt-4 max-w-[48ch] text-white/70">Create an account, drop in your PDFs, and copy the embed code.</p>
              <Link to={org ? '/app' : '/register'} className="btn btn-primary relative mt-8 !px-6 !py-3 !text-base">Start free <ArrowRight size={18} weight="bold" /></Link>
            </div>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-muted sm:px-6">
          <Logo size={22} />
          <p>Knowledge and decision assistant. Local models by default, no data leaves your machine.</p>
        </div>
      </footer>
    </div>
  )
}
