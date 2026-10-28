/** NFR: rate limit on auth routes (per client IP). */
import { afterAll, beforeEach, expect, it } from 'vitest'
import { PASSWORD, resetData, setupAuth, signUpBody } from './helpers.js'

const ctx = setupAuth({ authRate: { max: 3, window: 60 } })

beforeEach(() => resetData(ctx.pool))
afterAll(() => ctx.close())

it('limits sign-in attempts per IP and answers 429', async () => {
  const b = ctx.browser()
  await b.call('POST', '/sign-up/email', signUpBody(), '198.51.100.1')
  const attempt = (ip: string) => b.call('POST', '/sign-in/email', { email: 'nook@example.com', password: PASSWORD }, ip)
  const statuses = []
  for (let i = 0; i < 4; i++) statuses.push((await attempt('198.51.100.2')).status)
  expect(statuses).toEqual([200, 200, 200, 429])
  expect((await attempt('198.51.100.3')).status).toBe(200) // other clients unaffected
})
