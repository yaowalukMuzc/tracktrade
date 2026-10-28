import th from './locales/th.json'
import en from './locales/en.json'

type Messages = Record<string, unknown>

/**
 * Shared strings live in `locales/{th,en}.json`; each feature screen keeps its own namespace in
 * `locales/features/<feature>.<lang>.json` (one top-level key = the feature name), merged here.
 */
const parts = import.meta.glob<Messages>('./locales/features/*.json', { eager: true, import: 'default' })

function build(base: Messages, lang: 'th' | 'en'): Messages {
  const out: Messages = { ...base }
  for (const [path, part] of Object.entries(parts)) {
    if (!path.endsWith(`.${lang}.json`)) continue
    for (const [key, value] of Object.entries(part)) {
      if (key in out) throw new Error(`i18n: "${key}" from ${path} is already defined`)
      out[key] = value
    }
  }
  return out
}

export const messages = { th: build(th, 'th'), en: build(en, 'en') } as { th: typeof th; en: typeof en }
