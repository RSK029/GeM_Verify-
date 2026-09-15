import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { messageFor } from '@/api/errors'
import './auth.css'

/** Bidder self-registration only. Admins are seed-only, so no role field. */
export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '', email: '', password: '', company_name: '',
  })
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register({ ...form, name: form.name.trim(), email: form.email.trim() })
      navigate('/bidder', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card" style={{ maxWidth: 420 }}>
        <div className="auth-head">
          <span className="brand-mark" aria-hidden>GV</span>
          <div>
            <h1>Register your company</h1>
            <p className="small muted">Bidder access to GeMVerify</p>
          </div>
        </div>

        <form className="stack gap3" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="company">Company legal name</label>
            <input id="company" className="input" required minLength={2}
                   value={form.company_name} onChange={set('company_name')} />
            <span className="hint">
              Exactly as it appears on your PAN and incorporation certificate.
            </span>
          </div>
          <div className="field">
            <label htmlFor="name">Authorised signatory</label>
            <input id="name" className="input" required minLength={2}
                   value={form.name} onChange={set('name')} />
          </div>
          <div className="field">
            <label htmlFor="email">Email address</label>
            <input id="email" className="input" type="email" autoComplete="username"
                   required value={form.email} onChange={set('email')} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" className="input" type="password" minLength={8}
                   autoComplete="new-password" required
                   value={form.password} onChange={set('password')} />
            <span className="hint">At least 8 characters.</span>
          </div>

          {error != null && (
            <div className="banner banner-error">{messageFor(error)}</div>
          )}

          <button className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {busy ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="small muted auth-foot">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
