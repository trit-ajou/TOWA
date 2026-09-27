import type { Page } from '@playwright/test'

const E2E_PASSWORD = 'e2e-password'

/**
 * Sign up a fresh account through the login page's signup mode (the retired
 * dev-login form used to create-or-reuse by email alone). Each e2e email is
 * unique, so signup always creates the account. Returns once /library is reached.
 * Needs an invite code accepted by the target service engine (E2E_INVITE_CODE).
 */
export async function signUp(page: Page, email: string = `e2e-${Date.now()}@towa.test`, nickname?: string): Promise<void> {
  const inviteCode = process.env.E2E_INVITE_CODE
  if (!inviteCode) throw new Error('E2E_INVITE_CODE is required (a code from SERVICE_ENGINE_INVITE_CODES)')
  await page.goto('/login')
  await page.getByRole('button', { name: '회원가입' }).first().click()
  await page.locator('input[type=email]').fill(email)
  await page.locator('input[type=password]').fill(E2E_PASSWORD)
  await page.locator('input[placeholder="invite code"]').fill(inviteCode)
  if (nickname) await page.locator('input[autocomplete=nickname]').fill(nickname)
  await page.locator('button[type=submit]').click()
  await page.waitForURL(/\/library/, { timeout: 15_000 })
}

/** Clear browser-side state — fresh start, no auth/cache leakage between tests.
 *  Storage APIs can only be touched from a real same-origin document, so we
 *  navigate to the app's login page first.
 */
export async function clearBrowserState(page: Page): Promise<void> {
  await page.context().clearCookies()
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
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
