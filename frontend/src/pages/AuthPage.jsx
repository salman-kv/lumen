import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowRight, FilePdf, CircleNotch, Eye, EyeSlash, CheckCircle } from '@phosphor-icons/react'
import { toast } from 'sonner'
import { useAuth } from '../auth'
import { Logo, ThemeToggle } from '../components/ui'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function Field({ id, label, error, hint, children }) {
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      {children}
      {error ? <p role="alert" className="mt-1.5 text-[13px] font-medium text-bad">{error}</p> : hint && <p className="mt-1.5 text-[13px] text-muted">{hint}</p>}
    </div>
  )
}

function BrandPanel() {
  const reduce = useReducedMotion()
  const docs = [['Scholarship_Rules.pdf', 'p.1'], ['Leave_Policy.pdf', 'p.3'], ['Fee_Policy.pdf', 'p.2']]
  return (
    <div className="relative hidden overflow-hidden bg-[#0c1210] p-12 text-white lg:flex lg:flex-col lg:justify-between">
      <div aria-hidden className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(circle at 80% 10%, rgb(47 199 158 / 0.28), transparent 50%)' }} />
      <Logo />
      <div className="relative">
        <h2 className="max-w-[16ch] text-4xl font-semibold leading-[1.08] tracking-tighter">Turn policy PDFs into answers people trust.</h2>
        <p className="mt-4 max-w-[40ch] leading-relaxed text-white/65">Every reply names the document and page it came from, and eligibility questions are decided by checks you can inspect.</p>
        <div className="mt-10 space-y-3">
          {docs.map(([d, p], i) => (
            <motion.div key={d} initial={reduce ? false : { opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.15, type: 'spring', stiffness: 120, damping: 18 }}
              className="flex w-fit items-center gap-3 rounded-xl border border-white/10 bg-white/[0.06] px-4 py-2.5 text-sm backdrop-blur" style={{ marginLeft: i * 28 }}>
              <motion.span animate={reduce ? undefined : { y: [0, -3, 0] }} transition={{ duration: 3 + i, repeat: Infinity, ease: 'easeInOut' }}><FilePdf size={20} weight="duotone" className="text-[#2fc79e]" /></motion.span>
              {d}<span className="rounded-md bg-white/10 px-1.5 font-mono text-xs text-white/70">{p}</span>
            </motion.div>
          ))}
        </div>
      </div>
      <p className="relative text-sm text-white/50">Private by default. Each organization has its own isolated knowledge base.</p>
    </div>
  )
}

export default function AuthPage({ mode }) {
  const isReg = mode === 'register'
  const { org, login, register } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [f, setF] = useState({ org_name: '', email: '', password: '' })
  const [touched, setTouched] = useState({})
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  if (org) return <Navigate to={loc.state?.from?.startsWith('/app') ? loc.state.from : '/app'} replace />

  const errors = {
    org_name: isReg && f.org_name.trim().length < 2 ? 'Enter your organization name (at least 2 characters).' : '',
    email: !EMAIL.test(f.email.trim()) ? 'Enter a valid email address.' : '',
    password: isReg ? (f.password.length < 8 ? 'Use at least 8 characters.' : '') : (!f.password ? 'Enter your password.' : ''),
  }
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setFormError('') }
  const blur = (k) => () => setTouched({ ...touched, [k]: true })
  const strength = [f.password.length >= 8, /[A-Z]/.test(f.password) && /[a-z]/.test(f.password), /\d/.test(f.password), f.password.length >= 12].filter(Boolean).length

  async function submit(e) {
    e.preventDefault()
    setTouched({ org_name: true, email: true, password: true })
    if (Object.values(errors).some(Boolean)) return
    setBusy(true); setFormError('')
    try {
      if (isReg) { await register({ org_name: f.org_name.trim(), email: f.email.trim(), password: f.password }); toast.success('Welcome aboard! Let us set up your assistant.') }
      else await login({ email: f.email.trim(), password: f.password })
      nav('/app', { replace: true })
    } catch (err) { setFormError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-2">
      <main className="flex flex-col px-4 py-6 sm:px-10">
        <div className="flex items-center justify-between"><Link to="/" aria-label="Lumen home"><Logo /></Link><ThemeToggle /></div>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
            <h1 className="text-3xl font-semibold tracking-tighter">{isReg ? 'Create your organization' : 'Welcome back'}</h1>
            <p className="mt-2 text-muted">{isReg ? 'Set up a private assistant in a few minutes.' : 'Sign in to manage your knowledge base.'}</p>
            <form onSubmit={submit} noValidate className="mt-8 space-y-5">
              {isReg && (
                <Field id="org_name" label="Organization name" error={touched.org_name && errors.org_name}>
                  <input id="org_name" className="input" autoComplete="organization" value={f.org_name} onChange={set('org_name')} onBlur={blur('org_name')} placeholder="Northfield University" />
                </Field>
              )}
              <Field id="email" label="Work email" error={touched.email && errors.email}>
                <input id="email" type="email" className="input" autoComplete="email" value={f.email} onChange={set('email')} onBlur={blur('email')} placeholder="you@organization.com" />
              </Field>
              <Field id="password" label="Password" error={touched.password && errors.password}
                hint={isReg && !errors.password && f.password ? 'Looks good.' : isReg ? 'At least 8 characters.' : ''}>
                <div className="relative">
                  <input id="password" type={show ? 'text' : 'password'} className="input !pr-11" autoComplete={isReg ? 'new-password' : 'current-password'} value={f.password} onChange={set('password')} onBlur={blur('password')} />
                  <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink" aria-label={show ? 'Hide password' : 'Show password'}>
                    {show ? <EyeSlash size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {isReg && f.password && (
                  <div className="mt-2 flex gap-1.5" aria-hidden>
                    {[0, 1, 2, 3].map((i) => <motion.span key={i} className="h-1 flex-1 rounded-full" animate={{ backgroundColor: i < strength ? 'var(--accent)' : 'var(--line)' }} />)}
                  </div>
                )}
              </Field>
              {formError && <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} role="alert" className="rounded-xl bg-bad-soft px-3.5 py-2.5 text-sm font-medium text-bad">{formError}</motion.p>}
              <button className="btn btn-primary w-full !py-3" disabled={busy}>
                {busy ? <CircleNotch size={18} className="animate-spin" /> : <>{isReg ? 'Create account' : 'Sign in'} <ArrowRight size={16} weight="bold" /></>}
              </button>
            </form>
            <p className="mt-6 text-sm text-muted">
              {isReg ? 'Already have an account?' : 'New here?'}{' '}
              <Link to={isReg ? '/login' : '/register'} className="font-semibold text-accent underline-offset-2 hover:underline">{isReg ? 'Sign in' : 'Create an account'}</Link>
            </p>
            {!isReg && (
              <p className="mt-5 flex items-start gap-2 rounded-xl bg-surface-2 p-3 text-[13px] text-muted"><CheckCircle size={16} className="mt-0.5 shrink-0 text-accent" />
                <span>Demo accounts are created by the seed script. See the README for the email and password.</span></p>
            )}
          </motion.div>
        </div>
      </main>
      <BrandPanel />
    </div>
  )
}
