import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { messageFor } from '@/api/errors'
import './auth.css'

export default function Login() {
  const { login, expired, clearExpired } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    clearExpired()
    try {
      // The role comes from the database. There is deliberately no role
      // selector here — the caller does not get to choose what they are.
      const user = await login(email.trim(), password)
      navigate(user.role === 'ADMIN' ? '/admin' : '/bidder', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <div className="auth-head">
          <span className="brand-mark" aria-hidden>GV</span>
          <div>
            <h1>GeMVerify</h1>
            <p className="small muted">Government e-Marketplace bid verification</p>
          </div>
        </div>

        {expired && (
          <div className="banner banner-warn" style={{ marginBottom: 'var(--s4)' }}>
            Your session has ended. Please sign in again.
          </div>
        )}

        <form className="stack gap4" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error != null && (
            <div className="banner banner-error">{messageFor(error)}</div>
          )}

          <button className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="small muted auth-foot">
          Bidder without an account? <Link to="/register">Register your company</Link>
          <br />
          Administrator accounts are provisioned by the department.
        </p>
      </div>
    </div>
  )
}
