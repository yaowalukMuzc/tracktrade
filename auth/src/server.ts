/** HTTP entrypoint: serves Better Auth on `/api/auth/*` (health: `GET /api/auth/ok`). */
import { createServer } from 'node:http'
import { toNodeHandler } from 'better-auth/node'
import { createAuth } from './auth.js'
import { loadConfig } from './config.js'
import { smtpMailer } from './mailer.js'

const config = loadConfig()
const { auth, pool } = createAuth(config, { mailer: smtpMailer(config) })
const handler = toNodeHandler(auth)

const server = createServer((req, res) => {
  if (!req.url?.startsWith('/api/auth')) {
    res.writeHead(404, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ code: 'not_found', message: 'Not found', details: null }))
    return
  }
  void handler(req, res)
})

server.listen(config.port, () => console.log(`[auth] listening on :${config.port} (${config.env}), base ${config.baseUrl}`))

for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => {
    server.close(() => void pool.end().finally(() => process.exit(0)))
  })
}
