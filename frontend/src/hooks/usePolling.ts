import { useEffect, useRef } from 'react'

/**
 * Run `fn` every `ms` while `enabled`.
 *
 * Pauses whenever the tab is hidden (and fires once on the way back, so the
 * view is never stale after a tab switch), and clears on unmount. Overlapping
 * runs are suppressed: a slow response never queues a second request behind it.
 */
export function usePolling(
  fn: () => void | Promise<unknown>,
  ms: number,
  enabled = true,
) {
  const saved = useRef(fn)
  saved.current = fn

  useEffect(() => {
    if (!enabled || ms <= 0) return

    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    let inFlight = false

    const run = async () => {
      if (stopped || document.hidden || inFlight) return
      inFlight = true
      try {
        await saved.current()
      } catch {
        /* the caller owns error state; polling must not throw */
      } finally {
        inFlight = false
      }
    }

    const schedule = () => {
      timer = setTimeout(async () => {
        await run()
        if (!stopped) schedule()
      }, ms)
    }

    const onVisibility = () => {
      if (!document.hidden) void run()
    }

    document.addEventListener('visibilitychange', onVisibility)
    schedule()

    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [ms, enabled])
}
