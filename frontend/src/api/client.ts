// Thin fetch wrapper. Every backend error arrives as {error, message, details}
// (or FastAPI's {detail} for validation), and is normalised into ApiError.

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any

const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? '/api'
const TOKEN_KEY = 'skillsprint.token'

export class ApiError extends Error {
  status: number
  code: string
  details: Json
  constructor(status: number, code: string, message: string, details: Json = {}) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

let onUnauthorized: () => void = () => {}
export const setUnauthorizedHandler = (fn: () => void) => {
  onUnauthorized = fn
}

type Query = Record<string, string | number | boolean | undefined | null | string[]>

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v)) v.forEach((x) => params.append(k, x))
    else params.append(k, String(v))
  }
  const qs = params.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

async function toError(res: Response): Promise<ApiError> {
  let body: Json = null
  try {
    body = await res.json()
  } catch {
    /* not JSON */
  }
  if (body?.message) return new ApiError(res.status, body.error ?? 'error', body.message, body.details ?? {})
  if (Array.isArray(body?.detail)) {
    const msg = body.detail.map((d: Json) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ')
    return new ApiError(res.status, 'validation_error', msg, body.detail)
  }
  if (typeof body?.detail === 'string') return new ApiError(res.status, 'error', body.detail)
  return new ApiError(res.status, 'http_error', `${res.status} ${res.statusText}`)
}

async function request<T = Json>(method: string, path: string, opts: { query?: Query; body?: Json; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  let res: Response
  try {
    res = await fetch(buildUrl(path, opts.query), { method, headers, body })
  } catch {
    throw new ApiError(0, 'network', 'Cannot reach the API. Is the backend running on port 8000?')
  }
  if (res.status === 401 && path !== '/auth/login') {
    tokenStore.clear()
    onUnauthorized()
  }
  if (!res.ok) throw await toError(res)
  if (res.status === 204) return undefined as T
  const type = res.headers.get('content-type') ?? ''
  return (type.includes('application/json') ? res.json() : res.text()) as Promise<T>
}

export const api = {
  get: <T = Json>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T = Json>(path: string, body?: Json, query?: Query) => request<T>('POST', path, { body, query }),
  put: <T = Json>(path: string, body?: Json) => request<T>('PUT', path, { body }),
  patch: <T = Json>(path: string, body?: Json) => request<T>('PATCH', path, { body }),
  del: <T = Json>(path: string) => request<T>('DELETE', path),
  upload: <T = Json>(path: string, form: FormData) => request<T>('POST', path, { form }),
  /** Fetches a file with the auth header and hands it to the browser as a download. */
  async download(path: string, filename: string, query?: Query) {
    const headers: Record<string, string> = {}
    const token = tokenStore.get()
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(buildUrl(path, query), { headers })
    if (!res.ok) throw await toError(res)
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    // Firefox only follows links that are in the document, and revoking the
    // URL in the same tick can cancel the download, so wait before cleaning up.
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 30_000)
  },
}
