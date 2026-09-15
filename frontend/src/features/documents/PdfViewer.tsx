import { useEffect, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { useDocumentBlob } from '@/hooks/useDocumentBlob'
import { ErrorBanner, Spinner } from '@/components/Primitives'
import './pdf.css'

// Bundle the worker with the app rather than resolving it from a CDN at
// runtime; a CDN copy drifts from the pdfjs version react-pdf was built for.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

/**
 * Renders a bid document.
 *
 * The bytes are fetched with credentials and wrapped in a blob URL by
 * useDocumentBlob — GET /api/documents/{id} is authorised, and a plain
 * <iframe src> does not carry the session cookie, so it comes back 401.
 */
export function PdfViewer({
  documentId, filename,
}: {
  documentId: number | null
  filename?: string
}) {
  const { url, error, loading } = useDocumentBlob(documentId)
  const [pages, setPages] = useState(0)
  const [page, setPage] = useState(1)
  const [scale, setScale] = useState(1)
  const [width, setWidth] = useState(560)

  useEffect(() => { setPage(1); setPages(0) }, [documentId])

  // Fit the page to the pane, so the split view stays usable when the
  // evidence column is open.
  useEffect(() => {
    const el = document.getElementById('pdf-pane')
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      setWidth(Math.max(280, entry.contentRect.width - 32))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  if (documentId === null) {
    return (
      <div className="pdf-shell" id="pdf-pane">
        <div className="pdf-empty">Select a document to view it</div>
      </div>
    )
  }

  return (
    <div className="pdf-shell" id="pdf-pane">
      <div className="pdf-toolbar">
        <span className="pdf-name truncate" title={filename}>{filename ?? 'Document'}</span>
        <span className="grow" />
        {pages > 1 && (
          <span className="pdf-pager">
            <button className="btn btn-sm" disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)} aria-label="Previous page">‹</button>
            <span className="tnum small">{page} / {pages}</span>
            <button className="btn btn-sm" disabled={page >= pages}
                    onClick={() => setPage((p) => p + 1)} aria-label="Next page">›</button>
          </span>
        )}
        <span className="pdf-zoom">
          <button className="btn btn-sm" onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}
                  aria-label="Zoom out">−</button>
          <span className="tnum small">{Math.round(scale * 100)}%</span>
          <button className="btn btn-sm" onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}
                  aria-label="Zoom in">+</button>
        </span>
      </div>

      <div className="pdf-canvas">
        {loading && <div className="pdf-empty"><Spinner label="Loading document…" /></div>}
        {error != null && (
          <div style={{ padding: 'var(--s4)' }}>
            <ErrorBanner error={error} />
          </div>
        )}
        {url && (
          <Document
            file={url}
            onLoadSuccess={({ numPages }) => setPages(numPages)}
            loading={<div className="pdf-empty"><Spinner label="Rendering…" /></div>}
            error={<div className="pdf-empty">This document could not be rendered.</div>}
          >
            <Page
              pageNumber={page}
              width={width * scale}
              renderAnnotationLayer={false}
              renderTextLayer
            />
          </Document>
        )}
      </div>
    </div>
  )
}
