import { test, expect } from '@playwright/test'
import { devLogin, clearBrowserState, expireSession } from './helpers/auth'

// Category 5: 401 → /login redirect (#39 §401 분기)
test.describe('auth: 401 routing', () => {
  test.beforeEach(async ({ page }) => {
    await clearBrowserState(page)
  })

  test('triggering an authenticated request with a busted session bounces to /login?expired=1', async ({ page }) => {
    await devLogin(page)
    await expireSession(page)

    // Trigger any authenticated query — opening /library refetches projects.
    await page.goto('/library')

    // The global 401 handler navigates to /login with the expired marker.
    await page.waitForURL(/\/login\?expired=1/, { timeout: 15_000 })
    await expect(page.getByText('세션이 만료')).toBeVisible()
  })
})
