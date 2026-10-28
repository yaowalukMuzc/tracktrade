import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, getAccessToken, onSessionLost, setAccessToken } from './client'

const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('api client', () => {
  const fetchMock = vi.fn<typeof fetch>()
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken('old')
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('sends the bearer token', async () => {
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }))
    await api('/me')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/me')
    expect((init!.headers as Record<string, string>).Authorization).toBe('Bearer old')
  })

  it('refreshes once on 401 and retries with the new token', async () => {
    fetchMock
      .mockResolvedValueOnce(json(401, { code: 'token_expired', message: 'expired' }))
      .mockResolvedValueOnce(json(200, { token: 'new' }))
      .mockResolvedValueOnce(json(200, { id: 'u1' }))
    await expect(api('/me')).resolves.toEqual({ id: 'u1' })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/auth/token')
    expect((fetchMock.mock.calls[2][1]!.headers as Record<string, string>).Authorization).toBe('Bearer new')
    expect(getAccessToken()).toBe('new')
  })

  it('shares one refresh between concurrent 401s', async () => {
    fetchMock.mockImplementation(async (url, init) => {
      if (String(url).endsWith('/api/auth/token')) return json(200, { token: 'new' })
      const auth = (init!.headers as Record<string, string>).Authorization
      return auth === 'Bearer new' ? json(200, {}) : json(401, {})
    })
    await Promise.all([api('/a'), api('/b')])
    expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/api/auth/token'))).toHaveLength(1)
  })

  it('reports session loss when refresh fails', async () => {
    const lost = vi.fn()
    onSessionLost(lost)
    fetchMock.mockResolvedValueOnce(json(401, {})).mockResolvedValueOnce(json(401, { code: 'UNAUTHORIZED' }))
    await expect(api('/me')).rejects.toBeInstanceOf(ApiError)
    expect(lost).toHaveBeenCalledOnce()
    expect(getAccessToken()).toBeNull()
  })

  it('normalises {code, message, details} errors', async () => {
    fetchMock.mockResolvedValueOnce(json(422, { code: 'validation_error', message: 'bad', details: [{ field: 'password' }] }))
    const err = (await api('/me', { method: 'PATCH', body: {}, auth: false }).catch((e) => e)) as ApiError
    expect(err).toMatchObject({ status: 422, code: 'validation_error', message: 'bad', details: [{ field: 'password' }] })
  })
})
