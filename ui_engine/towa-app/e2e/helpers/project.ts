import type { Page } from '@playwright/test'

/**
 * Create a project from the library "+ → 새 프로젝트" modal and upload a
 * single in-memory PNG so the project has one page to navigate to.
 */
export async function createProjectWithOnePage(page: Page, name: string): Promise<string> {
  // Open the create project modal via AddMenu in the library header.
  await page.getByRole('button', { name: '추가' }).first().click()
  await page.getByRole('menuitem', { name: '새 프로젝트' }).click()

  // Fill the form.
  await page.getByLabel('이름').fill(name)
  // Drop a synthesized PNG as the first page.
  const pngBytes = Uint8Array.from([
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
  await page.locator('input[type=file]').setInputFiles({
    name: 'page-1.png',
    mimeType: 'image/png',
    buffer: Buffer.from(pngBytes),
  })

  await page.getByRole('button', { name: /만들기|생성|시작/ }).click()

  // The library navigates to the new project on success.
  await page.waitForURL(/\/project\/[\w-]+/, { timeout: 15_000 })
  const url = new URL(page.url())
  const match = url.pathname.match(/\/project\/([^/]+)/)
  if (!match) throw new Error(`Project URL not matched: ${page.url()}`)
  return match[1]
}
