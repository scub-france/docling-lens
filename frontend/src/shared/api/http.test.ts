import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from './http'

function mockResponse(status: number, body: unknown, isJson = true): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'Mock',
    json: () => (isJson ? Promise.resolve(body) : Promise.reject(new Error('not json'))),
    text: () => Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
  } as unknown as Response
}

const originalFetch = globalThis.fetch

describe('apiFetch', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn() as unknown as typeof fetch
  })
  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('returns the parsed body on 2xx', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(mockResponse(200, { ok: true }))
    const out = await apiFetch<{ ok: boolean }>('/x')
    expect(out).toEqual({ ok: true })
  })

  it('throws ApiError with status + structured detail on plain HTTPException', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      mockResponse(503, { detail: 'reasoning disabled' }),
    )
    await expect(apiFetch('/x')).rejects.toMatchObject({
      status: 503,
      detail: { detail: 'reasoning disabled' },
      message: 'HTTP 503: reasoning disabled',
    })
  })

  it('flattens Pydantic 422 detail arrays into a readable message', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      mockResponse(422, {
        detail: [
          { loc: ['body', 'query'], msg: 'Field required', type: 'missing' },
          { loc: ['body', 'modelId'], msg: 'value is not a valid string', type: 'type_error' },
        ],
      }),
    )
    try {
      await apiFetch('/x', { method: 'POST' })
      throw new Error('should have thrown')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      const err = e as ApiError
      expect(err.status).toBe(422)
      expect(err.message).toContain('body.query: Field required')
      expect(err.message).toContain('body.modelId: value is not a valid string')
    }
  })

  it('falls back to statusText when the body is not JSON', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(mockResponse(500, 'boom', false))
    await expect(apiFetch('/x')).rejects.toMatchObject({
      status: 500,
      message: expect.stringContaining('boom'),
    })
  })

  it('returns undefined on 204', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(mockResponse(204, null))
    expect(await apiFetch<undefined>('/x')).toBeUndefined()
  })
})
