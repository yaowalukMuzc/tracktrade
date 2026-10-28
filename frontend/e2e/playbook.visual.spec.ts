import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { apiCall, prefs, seedAccounts, signUp } from './helpers'

// Phase 2 visual + flow check of the Playbook (F-04): screens/web/13-WPlaybook.png, screens/mobile/21-Playbook.png,
// screens/mobile/22-SetupDetail.png. Seeds the four setups of the design + two example images, both themes.
// Stats stay "—" (computed from trades in Phase 7). Screenshots → docs/qa/phase-2/.
const out = (name: string) => `../docs/qa/phase-2/${name}.png`

const SETUPS = [
  {
    name: 'London Breakout',
    description: 'รอ Asia range แล้วเข้าเมื่อ London เบรก high/low พร้อม pullback เข้า zone และแท่ง confirm บน M15',
    timeframes: ['M15', 'H1'],
    sessions: ['london'],
    default_risk_pct: '1',
    management_rules: { partial: { pct: '50', at_r: '1.5' }, break_even: { at_r: '1' }, trailing: { method: 'Swing low M15' } },
    checklist: [
      { text: 'H4 bias ตรงทิศทาง', is_required: true },
      { text: 'ราคาอยู่ใน demand / supply zone', is_required: false },
      { text: 'มีแท่ง confirm บน M15', is_required: true },
      { text: 'ไม่มีข่าว high impact ใน 30 นาที', is_required: true },
    ],
  },
  {
    name: 'NY Reversal',
    description: 'Fade การ sweep high/low ของ London ช่วงเปิด New York เมื่อมี divergence บน M5',
    timeframes: ['M5', 'M15'],
    sessions: ['new_york'],
    default_risk_pct: '0.75',
    management_rules: { partial: { pct: '50', at_r: '1' }, break_even: { at_r: '1' }, trailing: null },
    checklist: [{ text: 'Sweep high/low ของ London', is_required: true }],
  },
  {
    name: 'Asia Range',
    description: 'เล่นในกรอบ Asia session เมื่อ ATR ต่ำ',
    timeframes: ['M15'],
    sessions: ['asia'],
    default_risk_pct: '0.5',
    checklist: [{ text: 'ATR ต่ำกว่าค่าเฉลี่ย', is_required: true }],
  },
  {
    name: 'News Fade',
    description: 'สวนแรงเหวี่ยงหลังข่าว 15 นาที — ทดลอง',
    timeframes: ['M5'],
    sessions: ['new_york'],
    default_risk_pct: '0.5',
    checklist: [],
  },
]

/** Draws a small candlestick-ish PNG in the page (no binary fixtures in the repo). */
async function chartPng(page: Page, seed: number): Promise<Buffer> {
  const b64 = await page.evaluate((s) => {
    const c = document.createElement('canvas')
    c.width = 480
    c.height = 300
    const g = c.getContext('2d')!
    g.fillStyle = 'hsl(48 22% 92%)'
    g.fillRect(0, 0, 480, 300)
    let y = 150
    for (let i = 0; i < 24; i++) {
      const d = Math.sin(i * 0.7 + s) * 28 + (s % 2 ? -4 : 4)
      const up = d > 0
      g.fillStyle = up ? 'hsl(150 45% 40%)' : 'hsl(355 60% 50%)'
      g.fillRect(16 + i * 19, Math.min(y, y - d), 11, Math.max(4, Math.abs(d)))
      g.fillRect(21 + i * 19, Math.min(y, y - d) - 10, 1, Math.abs(d) + 20)
      y -= d * 0.4
    }
    return c.toDataURL('image/png').split(',')[1]
  }, seed)
  return Buffer.from(b64, 'base64')
}

async function seed(page: Page, request: APIRequestContext, token: string) {
  await seedAccounts(request, token)
  const created: { id: string }[] = []
  for (const s of SETUPS) created.push(await apiCall(request, token, 'POST', '/setups', s))
  // One archived setup, as in the design's "Archived 1".
  const old = await apiCall<{ id: string }>(request, token, 'POST', '/setups', { name: 'Old Breakout', timeframes: ['H1'], sessions: ['london'] })
  await apiCall(request, token, 'POST', `/setups/${old.id}/archive`)
  for (const [i, note] of ['ตัวอย่าง A+', 'ไม่ควรเข้า'].entries()) {
    const res = await request.post('/api/v1/attachments', {
      headers: { Authorization: `Bearer ${token}` },
      multipart: { file: { name: `ex${i}.png`, mimeType: 'image/png', buffer: await chartPng(page, i + 1) } },
    })
    expect(res.ok()).toBeTruthy()
    const att = (await res.json()) as { id: string }
    await apiCall(request, token, 'POST', `/setups/${created[0].id}/examples`, { attachment_id: att.id, note })
  }
  return created
}

for (const theme of ['light', 'dark'] as const) {
  test(`playbook (${theme})`, async ({ page }, info) => {
    test.setTimeout(90_000)
    await prefs(page, theme, 'th')
    await page.goto('/login')
    const { token } = await signUp(page, { theme })
    const [london] = await seed(page, page.request, token)
    const mobile = info.project.name === 'mobile'

    await page.goto('/playbook')
    await expect(page.getByRole('radio', { name: 'ใช้งาน 4' }).first()).toBeVisible()
    if (!mobile) {
      // Desktop selects the first setup and keeps it in the URL.
      await expect(page).toHaveURL(new RegExp(`setup=${london.id}`))
      await expect(page.getByRole('heading', { name: 'London Breakout' })).toBeVisible()
      await expect(page.getByText('50% ที่ 1.5R')).toBeVisible()
      await expect(page.getByRole('img', { name: 'ตัวอย่าง A+' })).toBeVisible()
      await page.waitForFunction(() => [...document.images].filter((i) => i.src.startsWith('blob:')).every((i) => i.complete) && document.querySelectorAll('img[src^="blob:"]').length >= 2)
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: out(`playbook-desktop-${theme}`), fullPage: true })

      if (theme === 'light') {
        // Selection survives a reload; /playbook/:id shows the same split view.
        await page.getByRole('button', { name: /NY Reversal/ }).click()
        await expect(page.getByRole('heading', { name: 'NY Reversal' })).toBeVisible()
        await page.reload()
        await expect(page.getByRole('heading', { name: 'NY Reversal' })).toBeVisible()
        await page.goto(`/playbook/${london.id}`)
        await expect(page.getByRole('heading', { name: 'London Breakout' })).toBeVisible()

        // Checklist: keyboard reorder + add, saved to the API with ids kept.
        await page.getByRole('button', { name: 'ย้ายลำดับ: ราคาอยู่ใน demand / supply zone' }).focus()
        await page.keyboard.press('ArrowUp')
        await page.getByRole('button', { name: 'เพิ่ม', exact: true }).first().click()
        await page.getByLabel('ข้อใหม่ใน checklist').fill('RR อย่างน้อย 1:2')
        await page.keyboard.press('Enter')
        await expect
          .poll(async () => (await apiCall<{ checklist: { text: string }[] }>(page.request, token, 'GET', `/setups/${london.id}`)).checklist.map((c) => c.text))
          .toEqual(['ราคาอยู่ใน demand / supply zone', 'H4 bias ตรงทิศทาง', 'มีแท่ง confirm บน M15', 'ไม่มีข่าว high impact ใน 30 นาที', 'RR อย่างน้อย 1:2'])

        // Tap an item → mark it required, then delete another.
        await page.getByRole('button', { name: 'แก้ไขข้อความ: RR อย่างน้อย 1:2' }).click()
        await page.locator('ol').getByRole('checkbox', { name: 'จำเป็น' }).check()
        await page.getByRole('button', { name: 'เสร็จ' }).click()
        await page.getByRole('button', { name: 'แก้ไขข้อความ: ราคาอยู่ใน demand / supply zone' }).click()
        await page.getByRole('button', { name: 'ลบข้อ: ราคาอยู่ใน demand / supply zone' }).click()
        await expect
          .poll(async () => (await apiCall<{ checklist: { text: string; is_required: boolean }[] }>(page.request, token, 'GET', `/setups/${london.id}`)).checklist)
          .toEqual([
            expect.objectContaining({ text: 'H4 bias ตรงทิศทาง' }),
            expect.objectContaining({ text: 'มีแท่ง confirm บน M15' }),
            expect.objectContaining({ text: 'ไม่มีข่าว high impact ใน 30 นาที' }),
            expect.objectContaining({ text: 'RR อย่างน้อย 1:2', is_required: true }),
          ])

        // Create: client validation, then a new setup.
        await page.getByRole('button', { name: 'สร้าง Setup' }).first().click()
        const dlg = page.getByRole('dialog')
        await dlg.getByLabel('Default risk ต่อเทรด').fill('12')
        await dlg.getByRole('button', { name: 'สร้าง Setup' }).click()
        await expect(dlg.getByText('กรุณาใส่ชื่อ Setup')).toBeVisible()
        await expect(dlg.getByText('ใส่ค่าระหว่าง 0.01–10%')).toBeVisible()
        await dlg.getByLabel('ชื่อ Setup').fill('Gold Pullback')
        await dlg.getByLabel('Default risk ต่อเทรด').fill('0.5')
        await dlg.getByRole('button', { name: 'M15' }).click()
        await dlg.getByRole('button', { name: 'London' }).click()
        await page.evaluate(() => document.fonts.ready)
        await page.screenshot({ path: out('playbook-desktop-form-light') })
        await dlg.getByRole('button', { name: 'สร้าง Setup' }).click()
        await expect(page.getByRole('heading', { name: 'Gold Pullback' })).toBeVisible()
        await expect(page.getByRole('radio', { name: 'ใช้งาน 5' })).toBeVisible()

        // Delete from the edit form (unused setup → gone).
        await page.getByRole('button', { name: 'แก้ไข' }).click()
        await page.getByRole('dialog').getByRole('button', { name: 'ลบ Setup' }).click()
        await page.getByRole('button', { name: 'ลบถาวร' }).click()
        await expect(page.getByRole('radio', { name: 'ใช้งาน 4' })).toBeVisible()
      }
    } else {
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: out(`playbook-mobile-${theme}`), fullPage: true })

      await page.getByRole('link', { name: 'เปิด London Breakout' }).click()
      await expect(page).toHaveURL(new RegExp(`/playbook/${london.id}$`))
      await expect(page.getByRole('heading', { name: 'London Breakout' })).toBeVisible()
      await expect(page.getByText('Default risk 1%')).toBeVisible()
      await page.waitForFunction(() => document.querySelectorAll('img[src^="blob:"]').length >= 2)
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: out(`playbook-mobile-detail-${theme}`), fullPage: true })
    }
  })
}
