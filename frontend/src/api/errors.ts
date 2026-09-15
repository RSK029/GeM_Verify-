/** The { detail, code } envelope, mapped to copy a person can act on. */

export interface ApiErrorBody {
  detail?: string
  code?: string
}

const COPY: Record<string, string> = {
  INVALID_CREDENTIALS: 'Incorrect email or password',
  FORBIDDEN: 'You do not have access to this',
  NOT_FOUND: 'Not found',
  FILE_TOO_LARGE: 'File exceeds the 10 MB limit',
  UNSUPPORTED_FILE_TYPE: 'Only PDF documents are accepted',
  BID_NOT_EDITABLE: 'This bid can no longer be changed',
  DUPLICATE_EMAIL: 'An account with this email already exists',
  NOT_AUTHENTICATED: 'Your session has ended. Please sign in again.',
}

/** Codes whose server `detail` is more useful than any fixed copy. */
const PREFER_DETAIL = new Set(['MISSING_REQUIRED_DOCUMENTS', 'VALIDATION_ERROR'])

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: string

  constructor(status: number, body: ApiErrorBody) {
    const code = body.code ?? 'UNKNOWN'
    const detail = body.detail ?? 'Something went wrong'
    const message =
      PREFER_DETAIL.has(code) ? detail : (COPY[code] ?? detail)
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }

  get isAuth() {
    return this.status === 401
  }
  get isNotFound() {
    return this.status === 404
  }
}

export function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) {
    // A network-level failure usually means the API is not running.
    if (err.message === 'Failed to fetch')
      return 'Cannot reach the verification service. Is the backend running?'
    return err.message
  }
  return 'Something went wrong'
}
