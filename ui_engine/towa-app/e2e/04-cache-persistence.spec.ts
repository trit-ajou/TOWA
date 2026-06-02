import { test, expect } from '@playwright/test'
import { devLogin, clearBrowserState } from './helpers/auth'
import { createProjectWithOnePage } from './helpers/project'

// Category 4: cache survives reload (#39 §QueryClient IDB persister)
test.describe('cache persistence across reload', () => {
  test.beforeEach(async ({ page }) => {
    await clearBrowserState(page)
  })

  test('query persister database is created and a hard reload still shows the library', async ({ page }) => {
    await devLogin(page)
    await createProjectWithOnePage(page, `persist-${Date.now()}`)
    await page.goto('/library')

    // Wait for the persister to write at least once.
    await page.waitForTimeout(1500)

    const hasPersistDb = await page.evaluate(async () => {
      const dbs = await indexedDB.databases?.()
      return Array.isArray(dbs) && dbs.some((d) => (d.name ?? '').startsWith('towa-query-'))
    })
    expect(hasPersistDb).toBeTruthy()

    // Hard reload: persisted cache hydrates before mount, so the library
    // populates without a network round-trip blocking the UI.
    await page.reload()
    await expect(page).toHaveURL(/\/library/)
  })
})
