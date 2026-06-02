import type { Page } from '@playwright/test'

/** Minimal 1×1 PNG bytes. */
const TINY_PNG = Uint8Array.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
  0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44, 0x41,
  0x54, 0x78, 0x9c, 0x63, 0xfa, 0xcf, 0x00, 0x00,
  0x00, 0x05, 0x00, 0x01, 0xa5, 0x65, 0x21, 0x6c,
  0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44,
  0xae, 0x42, 0x60, 0x82,
])

/**
 * Create a project from the library "+ → 새 프로젝트" modal and upload N PNGs
 * (default 1). Returns the project id.
 */
export async function createProjectWithPages(page: Page, name: string, pageCount: number = 1): Promise<string> {
  const files = Array.from({ length: pageCount }, (_, i) => ({
    name: `page-${i + 1}.png`,
    mimeType: 'image/png',
    buffer: Buffer.from(TINY_PNG),
  }))
  await page.locator('[data-add-menu-trigger]').first().click()
  await page.locator('[data-add-menu-popover]').getByText('새 프로젝트').click()
  await page.locator('input[placeholder*="원피스"]').fill(name)
  await page.locator('input[type=file]').setInputFiles(files)
  await page.getByRole('button', { name: /^생성/ }).click()
  await page.waitForURL(/\/project\/[\w-]+/, { timeout: 15_000 })
  const url = new URL(page.url())
  const match = url.pathname.match(/\/project\/([^/]+)/)
  if (!match) throw new Error(`Project URL not matched: ${page.url()}`)
  return match[1]
}

/** Backwards-compatible alias used by older specs. */
export function createProjectWithOnePage(page: Page, name: string): Promise<string> {
  return createProjectWithPages(page, name, 1)
}
