// Generates the temporary PWA icons ("TT" on brand-600 with on-brand text, PLAN §8.2) from tokens.json.
// Renders with Playwright's Chromium so no image library is needed. Run: npm run icons
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const root = fileURLToPath(new URL('..', import.meta.url))
const tokens = JSON.parse(readFileSync(new URL('../../design-system/tokens.json', import.meta.url), 'utf8'))
const color = (name) => tokens.color.tokens.find((t) => t.name === name).value.light
const fill = color('brand-600')
const ink = color('on-brand')

/** `pad` shrinks the glyph for maskable icons (safe zone = inner 80%). */
const svg = (size, { radius = 0.22, pad = 1 } = {}) => `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${size * radius}" fill="${fill}"/>
  <text x="50%" y="50%" dy="0.35em" text-anchor="middle" fill="${ink}"
    font-family="Inter, 'Segoe UI', Arial, sans-serif" font-weight="700" font-size="${size * 0.42 * pad}" letter-spacing="${-size * 0.01}">TT</text>
</svg>`

mkdirSync(`${root}/public`, { recursive: true })
writeFileSync(`${root}/public/favicon.svg`, svg(64))

const browser = await chromium.launch()
const page = await browser.newPage()
const shots = [
  ['pwa-192.png', 192, {}],
  ['pwa-512.png', 512, {}],
  ['pwa-maskable-512.png', 512, { radius: 0, pad: 0.8 }],
  ['apple-touch-icon.png', 180, { radius: 0 }],
]
for (const [file, size, opts] of shots) {
  await page.setViewportSize({ width: size, height: size })
  await page.setContent(`<html><body style="margin:0">${svg(size, opts)}</body></html>`)
  await page.screenshot({ path: `${root}/public/${file}`, omitBackground: true })
}
await browser.close()
console.log('icons written to public/')
