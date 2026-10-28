/**
 * Better Auth client (F-01, PLAN §5.3). Talks to the auth service on `/api/auth/*` (same origin, proxied),
 * which keeps the session in an httpOnly cookie. FastAPI calls use a short-lived JWT from `token()`.
 */
import { createAuthClient } from 'better-auth/client'
import { inferAdditionalFields, jwtClient } from 'better-auth/client/plugins'

export const authClient = createAuthClient({
  baseURL: typeof window === 'undefined' ? 'http://localhost' : window.location.origin,
  basePath: '/api/auth',
  plugins: [
    jwtClient(),
    // Sign-up also sets the user's language and timezone (F-01 AC3).
    inferAdditionalFields({
      user: {
        locale: { type: 'string', required: false },
        timezone: { type: 'string', required: false },
      },
    }),
  ],
})

/** A failed auth call. `code` is Better Auth's error code (e.g. `INVALID_EMAIL_OR_PASSWORD`). */
export class AuthError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = 'AuthError'
  }
}

type AuthResult<T> = { data: T; error: null } | { data: null; error: { status: number; code?: string; message?: string; statusText?: string } }

/** `{data, error}` → data, or throw AuthError. Network failures surface as status 0. */
export async function unwrap<T>(call: Promise<AuthResult<T>>): Promise<T> {
  let result: AuthResult<T>
  try {
    result = await call
  } catch (e) {
    throw new AuthError(0, 'NETWORK', e instanceof Error ? e.message : 'network error')
  }
  if (result.error) {
    const { status, code, message, statusText } = result.error
    throw new AuthError(status, code ?? `HTTP_${status}`, message ?? statusText ?? '')
  }
  return result.data
}
