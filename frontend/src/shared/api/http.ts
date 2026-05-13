/**
 * Thin fetch wrapper.
 *
 * Single point of contact between feature `api.ts` modules and the backend.
 * The error path normalizes whatever FastAPI / docling-serve sent us:
 *  - Pydantic 422s come back as `{ detail: [{loc, msg, type}, ...] }` —
 *    arrays get stringified rather than rendered as `[object Object]`.
 *  - Plain HTTPException 4xx/5xx come back as `{ detail: "string" }`.
 *  - Unparseable bodies fall back to `response.statusText`.
 *
 * In dev we rely on the Vite proxy (`/api` → http://localhost:8001), so a
 * path like `/api/reasoning` works without any base URL config.
 */

/**
 * Concrete error class so consumers can `instanceof ApiError` instead of
 * relying on a TypeScript shape assertion at the call site. The raw
 * server payload is exposed on `detail` for callers that want to
 * inspect it (e.g. surface Pydantic field errors in a form).
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function describeDetail(detail: unknown, fallback: string): string {
  if (detail == null) return fallback
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object' && detail !== null && 'detail' in detail) {
    const inner = (detail as { detail: unknown }).detail
    if (typeof inner === 'string') return inner
    if (Array.isArray(inner)) {
      // Pydantic 422 — flatten to "loc: msg" per error.
      const parts = inner
        .map((e) => {
          if (e && typeof e === 'object') {
            const loc = 'loc' in e ? (e as { loc: unknown }).loc : undefined
            const msg = 'msg' in e ? (e as { msg: unknown }).msg : undefined
            const path = Array.isArray(loc) ? loc.join('.') : String(loc ?? '')
            return path && msg ? `${path}: ${msg}` : String(msg ?? loc ?? '')
          }
          return String(e)
        })
        .filter(Boolean)
      if (parts.length > 0) return parts.join('; ')
    }
    return JSON.stringify(inner)
  }
  return JSON.stringify(detail)
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  })

  if (!res.ok) {
    let detail: unknown = undefined
    try {
      detail = await res.json()
    } catch {
      detail = await res.text().catch(() => undefined)
    }
    const message = `HTTP ${res.status}: ${describeDetail(detail, res.statusText)}`
    throw new ApiError(res.status, detail, message)
  }

  // 204 No Content etc.
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
