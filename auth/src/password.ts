/**
 * argon2id hashing (NFR: "hash password ด้วย argon2"), replacing Better Auth's default scrypt.
 *
 * Parameters equal argon2-cffi's defaults (t=3, m=64 MiB, p=4, 32-byte hash) used by the Phase 1
 * FastAPI auth, so the PHC strings migrated into `auth_accounts.password` verify unchanged (F-01 AC8).
 */
import { hash, verify, type Options } from '@node-rs/argon2'

const ARGON2ID = 2 as Options['algorithm'] // Algorithm.Argon2id (const enum, not importable at runtime)

export const ARGON2_OPTIONS: Options = {
  algorithm: ARGON2ID,
  timeCost: 3,
  memoryCost: 65536,
  parallelism: 4,
  outputLen: 32,
}

export function hashPassword(password: string): Promise<string> {
  return hash(password, ARGON2_OPTIONS)
}

export async function verifyPassword({ hash: hashed, password }: { hash: string; password: string }): Promise<boolean> {
  try {
    return await verify(hashed, password)
  } catch {
    return false // malformed / non-argon2 hash
  }
}
