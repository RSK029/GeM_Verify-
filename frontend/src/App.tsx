import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '@/auth/AuthContext'
import { AppShell } from '@/components/AppShell'
import type { NavItem } from '@/components/AppShell'
import { Loading } from '@/components/Primitives'
import type { Role } from '@/api/types'

import Login from '@/pages/Login'
import Register from '@/pages/Register'

import BidderOverview from '@/pages/bidder/Overview'
import BidderTenders from '@/pages/bidder/Tenders'
import BidderTenderDetail from '@/pages/bidder/TenderDetail'
import BidderMyBids from '@/pages/bidder/MyBids'
import BidderBidDetail from '@/pages/bidder/BidDetail'
import BidderSubmission from '@/pages/bidder/Submission'
import BidderNotifications from '@/pages/bidder/Notifications'
import BidderProfile from '@/pages/bidder/Profile'

import AdminOverview from '@/pages/admin/Overview'
import AdminBids from '@/pages/admin/AllBids'
import AdminBidReview from '@/pages/admin/BidReview'
import AdminCompare from '@/pages/admin/Compare'
import AdminAudit from '@/pages/admin/AuditLog'

const BIDDER_NAV: NavItem[] = [
  { to: '/bidder', label: 'Overview', end: true },
  { to: '/bidder/tenders', label: 'Available Tenders' },
  { to: '/bidder/bids', label: 'My Bids' },
  { to: '/bidder/notifications', label: 'Notifications' },
  { to: '/bidder/profile', label: 'Company Profile' },
]

const ADMIN_NAV: NavItem[] = [
  { to: '/admin', label: 'Overview', end: true },
  { to: '/admin/bids', label: 'All Bids' },
  { to: '/admin/compare', label: 'Compare Bids' },
  { to: '/admin/audit', label: 'Audit Log' },
]

const homeFor = (role: Role) => (role === 'ADMIN' ? '/admin' : '/bidder')

/**
 * Gate on the session the server reports. A bidder who lands on an admin
 * route is sent to their own portal, never shown a blank screen.
 */
function Protected({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <Loading label="Restoring session…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />
  return <>{children}</>
}

function BidderLayout({ children }: { children: ReactNode }) {
  return <AppShell nav={BIDDER_NAV} portal="Bidder">{children}</AppShell>
}

function AdminLayout({ children }: { children: ReactNode }) {
  return <AppShell nav={ADMIN_NAV} portal="Administration">{children}</AppShell>
}

export default function App() {
  const { user, loading } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to={homeFor(user.role)} replace /> : <Login />}
      />
      <Route
        path="/register"
        element={user ? <Navigate to={homeFor(user.role)} replace /> : <Register />}
      />

      {/* ------------------------------------------------------- bidder */}
      <Route
        path="/bidder/*"
        element={
          <Protected role="BIDDER">
            <BidderLayout>
              <Routes>
                <Route index element={<BidderOverview />} />
                <Route path="tenders" element={<BidderTenders />} />
                <Route path="tenders/:id" element={<BidderTenderDetail />} />
                <Route path="bids" element={<BidderMyBids />} />
                <Route path="bids/:id" element={<BidderBidDetail />} />
                <Route path="bids/:id/documents" element={<BidderSubmission />} />
                <Route path="notifications" element={<BidderNotifications />} />
                <Route path="profile" element={<BidderProfile />} />
                <Route path="*" element={<Navigate to="/bidder" replace />} />
              </Routes>
            </BidderLayout>
          </Protected>
        }
      />

      {/* -------------------------------------------------------- admin */}
      <Route
        path="/admin/*"
        element={
          <Protected role="ADMIN">
            <AdminLayout>
              <Routes>
                <Route index element={<AdminOverview />} />
                <Route path="bids" element={<AdminBids />} />
                <Route path="bids/:id" element={<AdminBidReview />} />
                <Route path="compare" element={<AdminCompare />} />
                <Route path="audit" element={<AdminAudit />} />
                <Route path="*" element={<Navigate to="/admin" replace />} />
              </Routes>
            </AdminLayout>
          </Protected>
        }
      />

      <Route
        path="*"
        element={
          loading
            ? <Loading label="Restoring session…" />
            : <Navigate to={user ? homeFor(user.role) : '/login'} replace />
        }
      />
    </Routes>
  )
}
