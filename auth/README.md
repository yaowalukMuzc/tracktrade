# TrackTrade auth service

[Better Auth](https://better-auth.com) on Node — serves `/api/auth/*` (spec F-01, `docs/PLAN.md` §5.3).

- email/password with argon2id (`src/password.ts`, same parameters as Phase 1 so old hashes still verify)
- sessions in `auth_sessions` (httpOnly cookie `tt.session_token`, "remember me" = 30 days)
- forgot / reset password by email (`src/mailer.ts`; link `/reset-password?token=…`, 1 hour, single use,
  revokes every session)
- `GET /api/auth/token` → 15-minute EdDSA JWT (`sub` = user id, `sid` = session id) that FastAPI verifies
  with `GET /api/auth/jwks`
- rate limit on sign-in / sign-up / reset (`RATE_LIMIT_AUTH`)

The tables are created by the backend's Alembic migrations; `src/auth.ts` maps every field to its
snake_case column. Change both together.

## Run

```sh
cd auth
npm install
cp .env.example .env     # DATABASE_URL, BETTER_AUTH_SECRET, SMTP_*
npm run dev              # :3000 — the Vite dev server proxies /api/auth here
```

Docker compose runs it as the `auth` service with Mailpit (http://localhost:8025) catching email.

## Test

Integration tests use a real Postgres (default: the backend's test container on :55432, database
`tracktrade_auth_test`, created automatically) and run the backend migrations first:

```sh
npm run type-check && npm test
```
