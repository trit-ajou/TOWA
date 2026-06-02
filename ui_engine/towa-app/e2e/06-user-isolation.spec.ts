import { test, expect } from '@playwright/test'
import { devLogin, clearBrowserState } from './helpers/auth'

// Category 6: per-user cache isolation (#39 §User namespace)
test.describe('user cache isolation', () => {
  test.beforeEach(async ({ page }) => {
    await clearBrowserState(page)
  })

  test('different user emails materialize as different IDB namespaces', async ({ page }) => {
    await devLogin(page, `alice-${Date.now()}@towa.test`)
    await page.waitForTimeout(1000)
    const dbsAfterFirst = await page.evaluate(async () => {
      const list = await indexedDB.databases?.()
      return Array.isArray(list) ? list.map((d) => d.name).filter(Boolean) as string[] : []
    })
    const firstUserDbs = dbsAfterFirst.filter((n) =>
      n.startsWith('towa-cache-') || n.startsWith('towa-query-'),
    )
    expect(firstUserDbs.length).toBeGreaterThan(0)

    // Log out, then log in as a different user.
    await page.evaluate(() => localStorage.removeItem('towa.auth.session'))
    await devLogin(page, `bob-${Date.now()}@towa.test`)
    await page.waitForTimeout(1500)

    const dbsAfterSecond = await page.evaluate(async () => {
      const list = await indexedDB.databases?.()
      return Array.isArray(list) ? list.map((d) => d.name).filter(Boolean) as string[] : []
    })
    const userDbs = dbsAfterSecond.filter((n) =>
      n.startsWith('towa-cache-') || n.startsWith('towa-query-'),
    )
    // Each user gets its own per-namespace DB; second login should add new entries.
    expect(userDbs.length).toBeGreaterThan(firstUserDbs.length)
  })
})
