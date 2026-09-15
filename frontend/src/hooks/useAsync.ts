import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '@/api/errors'

interface State<T> {
  data: T | null
  error: unknown
  loading: boolean
  /** True only for the first load, so refreshes do not flash a skeleton. */
  initial: boolean
}

/**
 * Load a value, with a `reload` that refreshes in place.
 * A 404 is surfaced as data:null + error, letting callers distinguish
 * "not generated yet" from a real failure (the explanation endpoint).
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
  opts: { enabled?: boolean } = {},
) {
  const enabled = opts.enabled ?? true
  const [state, setState] = useState<State<T>>({
    data: null, error: null, loading: enabled, initial: true,
  })
  const alive = useRef(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  const run = useCallback(async (quiet = false) => {
    if (!enabled) return
    if (!quiet) setState((s) => ({ ...s, loading: true }))
    try {
      const data = await fnRef.current()
      if (alive.current) setState({ data, error: null, loading: false, initial: false })
    } catch (error) {
      if (alive.current)
        setState((s) => ({ data: s.data, error, loading: false, initial: false }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled])

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false, initial: false })
      return
    }
    setState((s) => ({ ...s, loading: true, initial: s.data === null }))
    void run(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled])

  const notFound =
    state.error instanceof ApiError && state.error.isNotFound

  return {
    ...state,
    notFound,
    reload: () => run(true),
    setData: (d: T | null) =>
      setState((s) => ({ ...s, data: d, error: null })),
  }
}
