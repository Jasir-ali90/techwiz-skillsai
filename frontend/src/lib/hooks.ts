import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { toast } from './toast'

/** Loads data on mount and whenever deps change; `reload` refetches. */
export function useQuery<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn
  // Only the latest request may write state, so a slow earlier response
  // (e.g. from a filter the user has already changed) can't overwrite it.
  const latest = useRef(0)

  const reload = useCallback(async () => {
    const id = ++latest.current
    setLoading(true)
    setError(null)
    try {
      const result = await fnRef.current()
      if (id === latest.current) setData(result)
    } catch (e) {
      if (id === latest.current) setError(e instanceof ApiError ? e : new ApiError(0, 'error', String(e)))
    } finally {
      if (id === latest.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading, reload, setData }
}

/** Wraps an action: tracks running state, reports errors as toasts, optional success message. */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>, success?: string | ((r: R) => string)) {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<R | undefined>(undefined)

  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setRunning(true)
      setError(null)
      try {
        const r = await fn(...args)
        setResult(r)
        if (success) toast.success(typeof success === 'function' ? success(r) : success)
        return r
      } catch (e) {
        const err = e instanceof ApiError ? e : new ApiError(0, 'error', String(e))
        setError(err)
        toast.error(err.message)
        return undefined
      } finally {
        setRunning(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fn],
  )
  return { run, running, error, result, setResult }
}
