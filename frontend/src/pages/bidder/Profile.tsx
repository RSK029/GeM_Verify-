import { useAuth } from '@/auth/AuthContext'
import { FieldRow } from '@/components/Primitives'
import { formatDate } from '@/lib/format'

export default function Profile() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <div className="page-header">
        <h1>Company profile</h1>
        <p className="small muted">
          These details are on your account record and are compared against the
          documents you submit.
        </p>
      </div>

      <div className="card">
        <div className="card-header"><h2>Registered details</h2></div>
        <div className="card-body">
          <FieldRow label="Company legal name" value={user.company_name} />
          <FieldRow label="Authorised signatory" value={user.name} />
          <FieldRow label="Email address" value={user.email} />
          <FieldRow label="Account type" value={user.role === 'ADMIN' ? 'Administrator' : 'Bidder'} />
          <FieldRow label="Registered on" value={formatDate(user.created_at)} />
        </div>
      </div>

      <div className="banner banner-info" style={{ marginTop: 'var(--s4)' }}>
        The company name here should match the legal name on your PAN and
        incorporation certificate exactly. A difference is not a rejection, but
        it will be raised for a reviewer to look at.
      </div>
    </div>
  )
}
