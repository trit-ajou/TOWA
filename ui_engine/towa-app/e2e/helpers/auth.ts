import type { Page } from '@playwright/test'

const DEFAULT_EMAIL = 'e2e@towa.test'

/** Sign in via the dev-login form. Returns once /library is reached. */
export async function devLogin(page: Page, email: string = DEFAULT_EMAIL, nickname?: string): Promise<void> {
  await page.goto('/login')
  await page.locator('input[type=email]').fill(email)
  if (nickname) await page.locator('input[autocomplete=nickname]').fill(nickname)
  await page.locator('button[type=submit]').click()
  await page.waitForURL(/\/library/, { timeout: 15_000 })
}

/** Clear browser-side state — fresh start, no auth/cache leakage between tests. */
export async function clearBrowserState(page: Page): Promise<void> {
  await page.context().clearCookies()
  await page.evaluate(async () => {
    localStorage.clear()
    sessionStorage.clear()
    const dbs = await indexedDB.databases?.()
    if (Array.isArray(dbs)) {
      await Promise.all(
        dbs.filter((d) => d.name).map((d) => new Promise<void>((resolve) => {
          const req = indexedDB.deleteDatabase(d.name as string)
          req.onsuccess = () => resolve()
          req.onerror = () => resolve()
          req.onblocked = () => resolve()
        })),
      )
    }
  })
}

/** Invalidate the persisted session by stomping the storage key with garbage. */
export async function expireSession(page: Page): Promise<void> {
  await page.evaluate(() => {
    const raw = localStorage.getItem('towa.auth.session')
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      parsed.sessionKey = 'expired-test-key-0000'
      localStorage.setItem('towa.auth.session', JSON.stringify(parsed))
    } catch {
      // already broken
    }
  })
}
