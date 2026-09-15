import { useEffect, useState } from 'react'
import { documents } from '@/api/client'

/**
 * Fetch a document as a blob and hand back an object URL.
 *
 * GET /api/documents/{id} only answers an authorised caller. A plain
 * <iframe src> does not attach the session cookie to that subresource request
 * and comes back 401, so the bytes have to be fetched with credentials and
 * wrapped locally. The URL is revoked when the id changes or the viewer
 * unmounts — an admin opens a lot of these in one review session.
 */
export function useDocumentBlob(documentId: number | null) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (documentId === null) {
      setUrl(null)
      return
    }
    let revoked = false
    let objectUrl: string | null = null

    setLoading(true)
    setError(null)
    setUrl(null)

    documents
      .blob(documentId)
      .then((blob) => {
        if (revoked) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((e) => { if (!revoked) setError(e) })
      .finally(() => { if (!revoked) setLoading(false) })

    return () => {
      revoked = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [documentId])

  return { url, error, loading }
}
