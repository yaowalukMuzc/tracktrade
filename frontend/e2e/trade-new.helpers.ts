import { expect, type Page } from '@playwright/test'

// Shared by trade-new.flow.spec.ts and trade-new.visual.spec.ts (Phase 4, F-07).

export type Exec = { side: 'in' | 'out'; lot: string; price: string; time: string; commission?: string }

/** The design's SHORT XAUUSD trade (times are the trader's Asia/Bangkok wall clock). */
export const DESIGN_EXECUTIONS: Exec[] = [
  { side: 'in', lot: '0.30', price: '4402.10', time: '2026-10-09T13:20', commission: '2.10' },
  { side: 'in', lot: '0.20', price: '4404.80', time: '2026-10-09T13:41', commission: '1.40' },
  { side: 'out', lot: '0.25', price: '4388.00', time: '2026-10-09T14:30' },
  { side: 'out', lot: '0.25', price: '4379.50', time: '2026-10-09T15:05' },
]

export async function fillDialog(page: Page, e: Exec) {
  const dialog = page.getByTestId('exec-dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('radio', { name: e.side.toUpperCase() }).click()
  await dialog.getByTestId('exec-lot').fill(e.lot)
  await dialog.getByTestId('exec-price').fill(e.price)
  await dialog.getByTestId('exec-time').fill(e.time)
  if (e.commission) await dialog.getByTestId('exec-commission').fill(e.commission)
  await page.getByTestId('exec-save').click()
  await expect(dialog).toBeHidden()
}

/** Fill the form with the design trade: SHORT, SL 4412.40, TP 4371.00, 2 entries + 2 exits. */
export async function fillDesignTrade(page: Page) {
  await page.getByTestId('trade-dir-short').click()
  await page.getByTestId('trade-sl').fill('4412.40')
  await page.getByTestId('trade-tp').fill('4371.00')
  // The form starts with one blank entry row — fill that one first.
  await page.getByTestId('exec-row').first().click()
  await fillDialog(page, DESIGN_EXECUTIONS[0])
  for (const e of DESIGN_EXECUTIONS.slice(1)) {
    await page.getByTestId(e.side === 'in' ? 'add-entry' : 'add-exit').click()
    await fillDialog(page, e)
  }
  await expect(page.getByTestId('exec-row')).toHaveCount(4)
}
