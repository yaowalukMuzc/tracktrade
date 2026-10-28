/**
 * Integration tests run against a real Postgres whose schema comes from the backend's Alembic
 * migrations (the single owner of the schema). Defaults match the backend's throwaway test container:
 *   AUTH_TEST_DATABASE_URL=postgresql://tracktrade:tracktrade@localhost:55432/tracktrade_auth_test
 * The database is created if missing, its schema dropped, then `alembic upgrade head` runs with the
 * backend's Python (BACKEND_PYTHON, default backend/.venv).
 */
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import pg from 'pg'

export const TEST_DB_URL =
  process.env.AUTH_TEST_DATABASE_URL ?? 'postgresql://tracktrade:tracktrade@localhost:55432/tracktrade_auth_test'

const backendDir = resolve(import.meta.dirname, '../../backend')

function backendPython(): string {
  if (process.env.BACKEND_PYTHON) return process.env.BACKEND_PYTHON
  const candidates = [resolve(backendDir, '.venv/Scripts/python.exe'), resolve(backendDir, '.venv/bin/python')]
  const found = candidates.find((p) => existsSync(p))
  if (!found) throw new Error('backend venv not found — run `uv sync` in backend/ or set BACKEND_PYTHON')
  return found
}

export default async function setup() {
  const url = new URL(TEST_DB_URL)
  const dbName = url.pathname.slice(1)
  const admin = new pg.Client({ connectionString: Object.assign(new URL(url), { pathname: '/postgres' }).toString() })
  await admin.connect()
  const exists = await admin.query('SELECT 1 FROM pg_database WHERE datname = $1', [dbName])
  if (exists.rowCount === 0) await admin.query(`CREATE DATABASE "${dbName.replace(/"/g, '')}"`)
  await admin.end()

  const db = new pg.Client({ connectionString: TEST_DB_URL })
  await db.connect()
  await db.query('DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;')
  await db.end()

  execFileSync(backendPython(), ['-m', 'alembic', 'upgrade', 'head'], {
    cwd: backendDir,
    env: { ...process.env, DATABASE_URL: TEST_DB_URL.replace(/^postgres(ql)?:\/\//, 'postgresql+asyncpg://') },
    stdio: 'inherit',
  })
}
