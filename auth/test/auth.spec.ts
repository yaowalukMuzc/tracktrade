/** F-01 on Better Auth: AC1 (sign-up rules), AC5–AC6 (forgot/reset), AC8 (Phase 1 users), JWT for FastAPI. */
import { createLocalJWKSet, jwtVerify } from 'jose'
import { afterAll, beforeEach, describe, expect, it } from 'vitest'
import { ORIGIN, PASSWORD, PHASE1_HASH, resetData, setupAuth, signUpBody } from './helpers.js'

const ctx = setupAuth()

beforeEach(async () => {
  await resetData(ctx.pool)
  ctx.outbox.length = 0
})
afterAll(() => ctx.close())

const count = async (sql: string, params: unknown[] = []) => Number((await ctx.pool.query(sql, params)).rows[0].n)

describe('sign-up (AC1)', () => {
  it('creates the user in `users` with locale/timezone and signs in', async () => {
    const b = ctx.browser()
    const res = await b.call('POST', '/sign-up/email', signUpBody('Nook@Example.com'))
    expect(res.status).toBe(200)
    expect(res.body?.user).toMatchObject({ email: 'nook@example.com', name: 'Nook Knight', locale: 'th', timezone: 'Asia/Bangkok' })

    const row = (await ctx.pool.query('SELECT * FROM users')).rows[0]
    expect(row).toMatchObject({ email: 'nook@example.com', display_name: 'Nook Knight', locale: 'th', theme: 'system', plan_tier: 'free', is_mentor: false })
    const account = (await ctx.pool.query('SELECT * FROM auth_accounts WHERE user_id = $1', [row.id])).rows[0]
    expect(account.provider_id).toBe('credential')
    expect(account.password).toMatch(/^\$argon2id\$v=19\$m=65536,t=3,p=4\$/)

    const session = await b.call('GET', '/get-session')
    expect(session.body?.user.id).toBe(row.id)
  })

  it('rejects passwords shorter than 8 characters', async () => {
    const res = await ctx.browser().call('POST', '/sign-up/email', signUpBody(undefined, { password: '1234567' }))
    expect(res.status).toBe(400)
    expect(res.body?.code).toBe('PASSWORD_TOO_SHORT')
    expect(await count('SELECT count(*) AS n FROM users')).toBe(0)
  })

  it('validates locale, timezone and name', async () => {
    for (const extra of [{ locale: 'fr' }, { timezone: 'Bangkok/Nowhere' }, { name: 'x'.repeat(101) }, { name: '   ' }]) {
      const res = await ctx.browser().call('POST', '/sign-up/email', signUpBody(undefined, extra))
      expect(res.status, JSON.stringify(extra)).toBe(400)
    }
    expect(await count('SELECT count(*) AS n FROM users')).toBe(0)
  })

  it('ignores server-managed fields (input: false)', async () => {
    await ctx.browser().call('POST', '/sign-up/email', signUpBody(undefined, { isMentor: true, planTier: 'pro', theme: 'dark' }))
    const row = (await ctx.pool.query('SELECT is_mentor, plan_tier, theme FROM users')).rows[0]
    expect(row).toEqual({ is_mentor: false, plan_tier: 'free', theme: 'system' })
  })

  it('rejects a duplicate email', async () => {
    await ctx.browser().call('POST', '/sign-up/email', signUpBody())
    const res = await ctx.browser().call('POST', '/sign-up/email', signUpBody())
    expect(res.status).toBe(422)
    expect(res.body?.code).toBe('USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL')
  })
})

describe('sign-in / sign-out', () => {
  it('signs in, then sign-out deletes the session', async () => {
    await ctx.browser().call('POST', '/sign-up/email', signUpBody())
    const b = ctx.browser()
    expect((await b.call('POST', '/sign-in/email', { email: 'nook@example.com', password: 'wrong-password' })).status).toBe(401)
    expect((await b.call('POST', '/sign-in/email', { email: 'nook@example.com', password: PASSWORD })).status).toBe(200)
    expect(await count('SELECT count(*) AS n FROM auth_sessions')).toBe(2) // sign-up + sign-in
    await b.call('POST', '/sign-out', {})
    expect(await count('SELECT count(*) AS n FROM auth_sessions')).toBe(1)
    expect((await b.call('GET', '/get-session')).body).toBeNull()
  })

  it('AC8: a Phase 1 user (migrated argon2-cffi hash) signs in without registering again', async () => {
    const { rows } = await ctx.pool.query(
      "INSERT INTO users (email, display_name, locale, timezone) VALUES ('old@example.com', 'Old User', 'en', 'Europe/London') RETURNING id",
    )
    await ctx.pool.query(
      "INSERT INTO auth_accounts (user_id, account_id, provider_id, password) VALUES ($1, $2, 'credential', $3)",
      [rows[0].id, rows[0].id, PHASE1_HASH],
    )
    const res = await ctx.browser().call('POST', '/sign-in/email', { email: 'old@example.com', password: PASSWORD })
    expect(res.status).toBe(200)
    expect(res.body?.user).toMatchObject({ id: rows[0].id, locale: 'en', timezone: 'Europe/London' })
  })
})

describe('JWT for FastAPI', () => {
  it('issues an EdDSA JWT with sub/sid/iss/aud that verifies against the JWKS', async () => {
    const b = ctx.browser()
    await b.call('POST', '/sign-up/email', signUpBody())
    const token = (await b.call('GET', '/token')).body?.token as string
    const jwks = (await b.call('GET', '/jwks')).body as { keys: { kid: string }[] }
    const { payload, protectedHeader } = await jwtVerify(token, createLocalJWKSet(jwks as never), {
      issuer: 'tracktrade-auth',
      audience: 'tracktrade-api',
    })
    const session = (await ctx.pool.query('SELECT id, user_id FROM auth_sessions')).rows[0]
    expect(protectedHeader.alg).toBe('EdDSA')
    expect(protectedHeader.kid).toBe(jwks.keys[0]?.kid)
    expect(payload).toMatchObject({ sub: session.user_id, sid: session.id })
    expect((payload.exp ?? 0) - (payload.iat ?? 0)).toBe(15 * 60)
    expect(payload).not.toHaveProperty('email')
  })

  it('refuses a token without a session', async () => {
    expect((await ctx.browser().call('GET', '/token')).status).toBe(401)
  })
})

describe('forgot / reset password (AC5–AC6)', () => {
  const resetLink = () => {
    const mail = ctx.outbox.at(-1)
    const match = mail?.text.match(/https?:\/\/\S+\/reset-password\?token=([\w-]+)/)
    return { mail, token: match?.[1] }
  }

  it('answers identically whether or not the email exists, and only mails existing users', async () => {
    await ctx.browser().call('POST', '/sign-up/email', signUpBody())
    const known = await ctx.browser().call('POST', '/request-password-reset', { email: 'nook@example.com', redirectTo: '/reset-password' })
    const unknown = await ctx.browser().call('POST', '/request-password-reset', { email: 'ghost@example.com', redirectTo: '/reset-password' })
    await ctx.flush()
    expect(known.status).toBe(200)
    expect(unknown.status).toBe(known.status)
    expect(unknown.body).toEqual(known.body)
    expect(ctx.outbox).toHaveLength(1)
    const { mail, token } = resetLink()
    expect(mail?.to).toBe('nook@example.com')
    expect(mail?.subject).toContain('ตั้งรหัสผ่านใหม่') // user locale = th
    expect(mail?.html).toContain(`${ORIGIN}/reset-password?token=${token}`)
    const expires = (await ctx.pool.query('SELECT expires_at FROM auth_verifications')).rows[0].expires_at as Date
    expect(Math.round((expires.getTime() - Date.now()) / 60_000)).toBe(60)
  })

  it('resets once, revokes every session, and the new password works', async () => {
    const b1 = ctx.browser()
    await b1.call('POST', '/sign-up/email', signUpBody())
    const b2 = ctx.browser()
    await b2.call('POST', '/sign-in/email', { email: 'nook@example.com', password: PASSWORD })
    expect(await count('SELECT count(*) AS n FROM auth_sessions')).toBe(2)

    await ctx.browser().call('POST', '/request-password-reset', { email: 'nook@example.com', redirectTo: '/reset-password' })
    await ctx.flush()
    const { token } = resetLink()
    expect(token).toBeTruthy()

    const short = await ctx.browser().call('POST', '/reset-password', { token, newPassword: 'short' })
    expect(short.status).toBe(400)

    const ok = await ctx.browser().call('POST', '/reset-password', { token, newPassword: 'brand-new-pass-9' })
    expect(ok.status).toBe(200)
    expect(await count('SELECT count(*) AS n FROM auth_sessions')).toBe(0)
    expect((await b1.call('GET', '/get-session')).body).toBeNull()

    const again = await ctx.browser().call('POST', '/reset-password', { token, newPassword: 'another-pass-10' })
    expect(again.status).toBe(400)

    const b3 = ctx.browser()
    expect((await b3.call('POST', '/sign-in/email', { email: 'nook@example.com', password: PASSWORD })).status).toBe(401)
    expect((await b3.call('POST', '/sign-in/email', { email: 'nook@example.com', password: 'brand-new-pass-9' })).status).toBe(200)
  })

  it('rejects an expired link', async () => {
    await ctx.browser().call('POST', '/sign-up/email', signUpBody())
    await ctx.browser().call('POST', '/request-password-reset', { email: 'nook@example.com', redirectTo: '/reset-password' })
    await ctx.flush()
    await ctx.pool.query("UPDATE auth_verifications SET expires_at = now() - interval '1 minute'")
    const res = await ctx.browser().call('POST', '/reset-password', { token: resetLink().token, newPassword: 'brand-new-pass-9' })
    expect(res.status).toBe(400)
  })
})
