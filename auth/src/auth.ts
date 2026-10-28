/**
 * Better Auth instance (F-01, PLAN §5.3).
 *
 * - Tables are owned by Alembic (`backend/alembic/versions/*_better_auth.py`); the `fields` maps
 *   below name every snake_case column. Keep the two in sync — Better Auth validates the schema
 *   at runtime and fails requests on a mismatch.
 * - FastAPI trusts the JWT from `GET /api/auth/token` (jwt plugin, EdDSA) verified via
 *   `GET /api/auth/jwks`; the `sid` claim lets it reject revoked sessions immediately.
 */
import { betterAuth, type BetterAuthOptions } from 'better-auth'
import { APIError } from 'better-auth/api'
import { jwt } from 'better-auth/plugins'
import { Pool } from 'pg'
import type { AuthConfig } from './config.js'
import { resetPasswordMail, type Mailer } from './mailer.js'
import { hashPassword, verifyPassword } from './password.js'
import { enumSchema, timezoneSchema } from './validation.js'

export const SESSION_TTL_SEC = 30 * 24 * 3600 // "remember me" lasts 30 days (Phase 1 refresh TTL)
export const RESET_TOKEN_TTL_SEC = 3600 // F-01 AC5
export const LOCALES = ['th', 'en'] as const
export const MAX_NAME_LENGTH = 100 // users.display_name varchar(100)

export interface AuthDeps {
  mailer: Mailer
  pool?: Pool
  /** Called with background work (emails) so tests can await it; defaults to fire-and-forget. */
  background?: (task: Promise<unknown>) => void
}

const ts = { createdAt: 'created_at', updatedAt: 'updated_at' } as const

function checkName(name: unknown) {
  if (typeof name === 'string' && (name.trim().length === 0 || name.length > MAX_NAME_LENGTH)) {
    throw new APIError('BAD_REQUEST', { message: `Name must be 1–${MAX_NAME_LENGTH} characters`, code: 'INVALID_NAME' })
  }
}

export function createAuth(config: AuthConfig, deps: AuthDeps) {
  const pool = deps.pool ?? new Pool({ connectionString: config.databaseUrl })
  const background = deps.background ?? ((task) => void task.catch((err) => console.error('[auth] background task failed', err)))
  const strict = config.authRate ?? { max: 0, window: 60 }

  const options = {
    appName: 'TrackTrade',
    baseURL: config.baseUrl,
    basePath: '/api/auth',
    secret: config.secret,
    trustedOrigins: config.trustedOrigins,
    database: pool,

    user: {
      modelName: 'users',
      fields: { name: 'display_name', emailVerified: 'email_verified', ...ts },
      additionalFields: {
        locale: { type: 'string', required: false, defaultValue: 'th', input: true, validator: { input: enumSchema(LOCALES) } },
        timezone: { type: 'string', required: false, defaultValue: 'Asia/Bangkok', input: true, validator: { input: timezoneSchema } },
        // Preferences/flags changed through FastAPI (`PATCH /me`) or later phases, never at sign-up.
        theme: { type: 'string', required: false, defaultValue: 'system', input: false },
        planTier: { type: 'string', required: false, defaultValue: 'free', input: false, fieldName: 'plan_tier' },
        isMentor: { type: 'boolean', required: false, defaultValue: false, input: false, fieldName: 'is_mentor' },
      },
    },
    session: {
      modelName: 'auth_sessions',
      fields: { expiresAt: 'expires_at', ipAddress: 'ip_address', userAgent: 'user_agent', userId: 'user_id', ...ts },
      expiresIn: SESSION_TTL_SEC,
      updateAge: 24 * 3600,
    },
    account: {
      modelName: 'auth_accounts',
      fields: {
        accountId: 'account_id',
        providerId: 'provider_id',
        userId: 'user_id',
        accessToken: 'access_token',
        refreshToken: 'refresh_token',
        idToken: 'id_token',
        accessTokenExpiresAt: 'access_token_expires_at',
        refreshTokenExpiresAt: 'refresh_token_expires_at',
        ...ts,
      },
    },
    verification: {
      modelName: 'auth_verifications',
      fields: { expiresAt: 'expires_at', ...ts },
    },

    emailAndPassword: {
      enabled: true,
      minPasswordLength: 8, // F-01 AC1
      maxPasswordLength: 128,
      autoSignIn: true,
      password: { hash: hashPassword, verify: verifyPassword },
      resetPasswordTokenExpiresIn: RESET_TOKEN_TTL_SEC,
      revokeSessionsOnPasswordReset: true, // F-01 AC6
      // F-01 AC5: our own link straight to the SPA page. Not awaited, so the response time does not
      // reveal whether the email exists (Better Auth answers the same either way).
      sendResetPassword: async ({ user, token }) => {
        const url = `${config.baseUrl}/reset-password?token=${encodeURIComponent(token)}`
        const locale = (user as { locale?: string }).locale
        background(deps.mailer.send(resetPasswordMail(user.email, user.name, locale, url)))
      },
    },

    databaseHooks: {
      user: {
        create: { before: async (user) => checkName(user.name) },
        update: { before: async (user) => checkName(user.name) },
      },
    },

    rateLimit: {
      enabled: config.authRate !== null,
      window: 60,
      max: 300, // everything else (get-session, token) — generous, the SPA polls these
      customRules: {
        '/sign-in/email': strict,
        '/sign-up/email': strict,
        '/request-password-reset': strict,
        '/reset-password': strict,
        '/change-password': strict,
      },
    },

    advanced: {
      cookiePrefix: 'tt',
      useSecureCookies: config.cookieSecure,
      database: { generateId: 'uuid' },
    },

    plugins: [
      jwt({
        jwks: { keyPairConfig: { alg: 'EdDSA', crv: 'Ed25519' } },
        jwt: {
          issuer: config.jwtIssuer,
          audience: config.jwtAudience,
          expirationTime: '15m',
          // `sub` = user id (default). Keep the payload minimal: FastAPI loads the user itself.
          definePayload: ({ session }) => ({ sid: session.id }),
        },
        schema: {
          jwks: {
            modelName: 'auth_jwks',
            fields: { publicKey: 'public_key', privateKey: 'private_key', createdAt: 'created_at', expiresAt: 'expires_at' },
          },
        },
      }),
    ],
  } satisfies BetterAuthOptions

  return { auth: betterAuth(options), pool }
}

export type Auth = ReturnType<typeof createAuth>['auth']
