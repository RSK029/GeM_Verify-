import { NavLink, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { useAuth } from '@/auth/AuthContext'
import { notifications as notifApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { usePolling } from '@/hooks/usePolling'
import { initials } from '@/lib/format'
import './appshell.css'

export interface NavItem {
  to: string
  label: string
  end?: boolean
}

export function AppShell({
  nav, children, portal,
}: {
  nav: NavItem[]
  children: ReactNode
  portal: 'Bidder' | 'Administration'
}) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const unread = useAsync(() => notifApi.list(true), [])
  usePolling(unread.reload, 8000)

  const count = unread.data?.unread_count ?? 0

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-brand">
          <span className="brand-mark" aria-hidden>GV</span>
          <div className="stack">
            <span className="brand-name">GeMVerify</span>
            <span className="brand-portal">{portal}</span>
          </div>
        </div>

        <div className="grow" />

        <NavLink
          to={portal === 'Bidder' ? '/bidder/notifications' : '/admin/bids'}
          className="notif-button"
          aria-label={`Notifications${count ? `, ${count} unread` : ''}`}
        >
          <BellIcon />
          {count > 0 && <span className="notif-badge tnum">{count > 9 ? '9+' : count}</span>}
        </NavLink>

        <div className="user-menu">
          <button
            className="user-button"
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <span className="avatar" aria-hidden>{initials(user?.name)}</span>
            <span className="stack user-text">
              <span className="user-name truncate">{user?.name}</span>
              <span className="user-role">{user?.role === 'ADMIN' ? 'Administrator' : 'Bidder'}</span>
            </span>
          </button>
          {menuOpen && (
            <>
              <div className="menu-scrim" onClick={() => setMenuOpen(false)} />
              <div className="menu" role="menu">
                <div className="menu-head">
                  <div className="strong truncate">{user?.name}</div>
                  <div className="small muted truncate">{user?.email}</div>
                  {user?.company_name && (
                    <div className="small muted truncate">{user.company_name}</div>
                  )}
                </div>
                {portal === 'Bidder' && (
                  <button
                    className="menu-item"
                    role="menuitem"
                    onClick={() => { setMenuOpen(false); navigate('/bidder/profile') }}
                  >
                    Company profile
                  </button>
                )}
                <button
                  className="menu-item menu-danger"
                  role="menuitem"
                  onClick={async () => { setMenuOpen(false); await logout(); navigate('/login') }}
                >
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      <div className="shell-body">
        <nav className="shell-nav" aria-label="Main">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="shell-main">{children}</main>
      </div>
    </div>
  )
}

function BellIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  )
}
