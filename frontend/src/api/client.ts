/**
 * The HTTP client. Two rules hold everywhere in this file:
 *
 *   1. credentials: 'include' on every call. The session is an httpOnly
 *      cookie named gv_session; JavaScript never reads it and nothing
 *      auth-related is ever written to localStorage.
 *   2. A 401 is not just an error — it means the session is gone. The client
 *      raises it to a subscriber (the auth context) so the app can clear
 *      state and route to /login from one place.
 */

import { ApiError } from './errors'
import type {
  AdminOverview, AiExplanation, AiStatus, AppNotification, AuditLogPage,
  BidDetail, BidderDashboard, BidSummary, BidVerification, ConsistencyReport,
  BidDocument, DocumentType, ExplanationKind, NotificationList, Tender, User,
  BidStatus, VerificationResult,
} from './types'

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  'http://localhost:8000/api'

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** The auth context registers here so 401 handling lives in one place. */
export function setUnauthorizedHandler(fn: UnauthorizedHandler | null) {
  onUnauthorized = fn
}

/** Set while the login request itself is in flight, so its own 401 (bad
 *  password) does not trigger the global "session expired" path. */
let suppressUnauthorized = false

async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: { raw?: boolean; suppress401?: boolean } = {},
): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        ...(init.body instanceof FormData
          ? {}
          : { 'Content-Type': 'application/json' }),
        ...(init.headers ?? {}),
      },
    })
  } catch {
    throw new Error('Failed to fetch')
  }

  if (res.status === 401 && !suppressUnauthorized && !opts.suppress401) {
    onUnauthorized?.()
  }

  if (!res.ok) {
    let body = {}
    try {
      body = await res.json()
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, body)
  }

  if (res.status === 204) return undefined as T
  if (opts.raw) return res as unknown as T
  return (await res.json()) as T
}

const get = <T>(p: string, o?: { suppress401?: boolean }) =>
  request<T>(p, { method: 'GET' }, o)
const post = <T>(p: string, body?: unknown) =>
  request<T>(p, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
const del = <T>(p: string) => request<T>(p, { method: 'DELETE' })

function qs(params: Record<string, string | number | boolean | undefined>) {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') s.set(k, String(v))
  }
  const out = s.toString()
  return out ? `?${out}` : ''
}

// ------------------------------------------------------------------ auth

export const auth = {
  async login(email: string, password: string): Promise<User> {
    suppressUnauthorized = true
    try {
      return await post<User>('/auth/login', { email, password })
    } finally {
      suppressUnauthorized = false
    }
  },
  register(input: {
    name: string
    email: string
    password: string
    company_name: string
  }): Promise<User> {
    return post<User>('/auth/register', input)
  },
  logout: () => post<void>('/auth/logout'),
  /** 401 here is the normal "not signed in" answer on boot, not an expiry. */
  me: () => get<User>('/auth/me', { suppress401: true }),
}

// --------------------------------------------------------------- tenders

export const tenders = {
  list: (status?: string) => get<Tender[]>(`/tenders${qs({ status })}`),
  get: (id: number) => get<Tender>(`/tenders/${id}`),
}

// ------------------------------------------------------------------ bids

export const bids = {
  listMine: (status?: BidStatus) => get<BidSummary[]>(`/bids${qs({ status })}`),
  get: (id: number) => get<BidDetail>(`/bids/${id}`),
  create: (tender_id: number) => post<BidDetail>('/bids', { tender_id }),
  submit: (id: number) => post<BidSummary>(`/bids/${id}/submit`),
  remove: (id: number) => del<void>(`/bids/${id}`),
  withdraw: (id: number) => post<BidSummary>(`/bids/${id}/withdraw`),
  /** Opens a fresh draft for the same tender; never revives the old bid. */
  reapply: (id: number) => post<BidSummary>(`/bids/${id}/reapply`),
  verification: (id: number) => get<BidVerification>(`/bids/${id}/verification`),
  consistency: (id: number) => get<ConsistencyReport>(`/bids/${id}/consistency`),
  explanation: (id: number, kind: ExplanationKind) =>
    get<AiExplanation>(`/bids/${id}/explanation${qs({ kind })}`),
  regenerate: (id: number, kind: ExplanationKind) =>
    post<void>(`/bids/${id}/explanation/regenerate`, { kind }),
}

// ------------------------------------------------------------- documents

export const documents = {
  meta: (id: number) => get<BidDocument>(`/documents/${id}/meta`),
  verification: (id: number) =>
    get<VerificationResult[]>(`/documents/${id}/verification`),

  /**
   * The PDF must be fetched and turned into a blob. A plain
   * <iframe src="/api/documents/{id}"> does not carry the session cookie
   * and comes back 401.
   */
  async blob(id: number): Promise<Blob> {
    const res = await request<Response>(
      `/documents/${id}`,
      { method: 'GET' },
      { raw: true },
    )
    return res.blob()
  },

  upload(bidId: number, documentType: DocumentType, file: File) {
    const fd = new FormData()
    fd.append('document_type', documentType)
    fd.append('file', file)
    return request<BidDocument>(`/bids/${bidId}/documents`, {
      method: 'POST',
      body: fd,
    })
  },

  resubmit(documentId: number, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    return request<BidDocument>(`/documents/${documentId}/resubmit`, {
      method: 'POST',
      body: fd,
    })
  },
}

// --------------------------------------------------------- notifications

export const notifications = {
  list: (unreadOnly = false) =>
    get<NotificationList>(`/notifications${qs({ unread_only: unreadOnly || undefined })}`),
  markRead: (id: number) => post<void>(`/notifications/${id}/read`),
  markAllRead: () => post<void>('/notifications/read-all'),
}

// ----------------------------------------------------------------- admin

export const admin = {
  overview: () => get<AdminOverview>('/admin/overview'),
  bids: (params: { status?: BidStatus; tender_id?: number; q?: string } = {}) =>
    get<BidSummary[]>(`/admin/bids${qs(params)}`),
  approve: (id: number, note: string) =>
    post<BidSummary>(`/admin/bids/${id}/approve`, { note }),
  reject: (id: number, reason: string) =>
    post<BidSummary>(`/admin/bids/${id}/reject`, { reason }),
  clarification: (id: number, document_ids: number[], message: string) =>
    post<BidSummary>(`/admin/bids/${id}/clarification`, { document_ids, message }),
  auditLogs: (params: {
    bid_id?: number
    user_id?: number
    limit?: number
    offset?: number
  } = {}) => get<AuditLogPage>(`/admin/audit-logs${qs(params)}`),
}

// -------------------------------------------------------------------- ai

export const ai = {
  /** Not in the contract; used only to caption the AI panel. */
  status: () => get<AiStatus>('/ai/status'),
}

export const dashboard = {
  bidder: () => get<BidderDashboard>('/dashboard'),
}

export type { AppNotification }
