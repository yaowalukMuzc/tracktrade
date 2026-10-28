# TrackTrade backend

FastAPI + async SQLAlchemy 2 + Alembic + arq (Redis) — Python 3.12, managed with [uv](https://docs.astral.sh/uv/).
Architecture: `docs/PLAN.md` §5. API contract: `docs/PLAN.md` §6 (all routes under `/api/v1`).
Authentication is the Better Auth service in `../auth` (PLAN §5.3): this API only verifies its JWTs
(JWKS from `AUTH_JWKS_URL`) and checks that the session is still alive in `auth_sessions`.
Alembic owns every table, including Better Auth's `auth_*` tables.

```
app/
  main.py            create_app() factory (routers, CORS, request-id, lifespan: DB, Redis, WS hub)
  health.py          GET /api/v1/health (DB + Redis)
  core/              config, db, models_base, security, access (owner filter -> 404),
                     errors ({code,message,details}), logging (structlog JSON), ratelimit, pubsub
  modules/<name>/    models · schemas · repo · service · router   (auth = Better Auth tables + JWT deps, users, symbols, …)
  realtime/          WS /api/v1/ws + per-process hub (Redis pub/sub `user:{id}` fan-out)
  worker/            arq WorkerSettings + jobs
  seeds/             *.yaml + `python -m app.seeds` (idempotent upsert)
alembic/             async migrations
tests/               pytest integration tests (real Postgres + Redis)
```

## Setup

```sh
cd backend
uv sync                      # creates .venv with runtime + dev deps from uv.lock
cp .env.example .env         # then edit DATABASE_URL / REDIS_URL / AUTH_JWKS_URL
```

Settings (env vars, see `.env.example`): `ENV`, `DATABASE_URL`, `REDIS_URL`, `AUTH_JWKS_URL`,
`JWT_ISSUER`, `JWT_AUDIENCE`, `JWKS_CACHE_SEC`, `CORS_ORIGINS`, `LOG_LEVEL`.

## Run

```sh
uv run alembic upgrade head                                          # migrate
uv run python -m app.seeds                                           # seed reference data
uv run uvicorn app.main:create_app --factory --reload --port 8000    # API  -> http://localhost:8000/api/v1/docs
uv run arq app.worker.settings.WorkerSettings                        # worker
```

Docker (one image): default command `scripts/start-api.sh` = migrate + seed + uvicorn on :8000;
the worker overrides the command with `arq app.worker.settings.WorkerSettings`.

## Test

Tests need Postgres 17 and Redis. Throwaway containers:

```sh
docker run -d --name tt-test-pg -p 55432:5432 \
  -e POSTGRES_USER=tracktrade -e POSTGRES_PASSWORD=tracktrade -e POSTGRES_DB=tracktrade_test postgres:17-alpine
docker run -d --name tt-test-redis -p 56379:6379 redis:7-alpine

uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest
```

Override with `TEST_DATABASE_URL` (default `postgresql+asyncpg://tracktrade:tracktrade@localhost:55432/tracktrade_test`)
and `TEST_REDIS_URL` (default `redis://localhost:56379/15`). The test session drops and rebuilds the
`public` schema via `alembic upgrade head`, seeds reference data, and cleans user rows + flushes the
Redis DB between tests — point it only at a disposable database.

## Migrations

```sh
uv run alembic revision --autogenerate -m "describe change"   # review the generated file!
uv run alembic upgrade head
uv run alembic downgrade -1
```

New models must be imported in `app/models.py` so autogenerate sees them.

## Conventions

- Every error response: `{code, message, details}` (`app/core/errors.py`).
- Ownership: repos take an `AccessContext` and filter by owner inside the query (`core/access.py`);
  someone else's id is indistinguishable from a missing one -> 404.
- Money/prices are `Decimal` and serialise as JSON strings.
- Realtime events: `core.pubsub.publish(redis, user_id, type, data)` from API or worker ->
  every socket of that user receives `{type, data, ts}`.
