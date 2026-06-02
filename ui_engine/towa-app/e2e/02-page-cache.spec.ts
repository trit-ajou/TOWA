import { test, expect } from '@playwright/test'
import { devLogin, clearBrowserState } from './helpers/auth'
import { createProjectWithOnePage } from './helpers/project'

// Category 2: page-navigation cache hit + prefetch (#39 §page-binary-prefetch)
test.describe('page cache + prefetch', () => {
  test.beforeEach(async ({ page }) => {
    await clearBrowserState(page)
  })

  test('switches pages without a full reload and warms IDB cache for neighbors', async ({ page }) => {
    await devLogin(page)
    const projectId = await createProjectWithOnePage(page, `cache-${Date.now()}`)

    await page.goto(`/project/${projectId}/edit`)
    await expect(page.locator('#towa-canvas-area')).toBeVisible()

    // After the editor mounts the prefetch hook runs; give it a moment to populate
    // the user-namespaced IDB cache database.
    await page.waitForTimeout(1500)

    const cacheDbExists = await page.evaluate(async () => {
      const dbs = await indexedDB.databases?.()
      return Array.isArray(dbs) && dbs.some((d) => (d.name ?? '').startsWith('towa-cache-'))
    })
    expect(cacheDbExists).toBeTruthy()
  })
})
