import { test, expect } from '@playwright/test'
import { devLogin, clearBrowserState } from './helpers/auth'
import { createProjectWithOnePage } from './helpers/project'

// Category 1: library → project → editor entry flow (#39 §메타지침)
test.describe('entry flow', () => {
  test.beforeEach(async ({ page }) => {
    await clearBrowserState(page)
  })

  test('logs in, opens library, creates a project, and reaches the editor', async ({ page }) => {
    await devLogin(page)
    await expect(page).toHaveURL(/\/library/)

    const name = `e2e-${Date.now()}`
    const projectId = await createProjectWithOnePage(page, name)
    expect(projectId).toBeTruthy()

    // Project home reachable.
    await expect(page).toHaveURL(new RegExp(`/project/${projectId}`))

    // Open editor.
    await page.goto(`/project/${projectId}/edit`)
    // Bitmappery canvas mount renders the toolbox; wait for it as a proxy for editor ready.
    await expect(page.locator('#towa-canvas-area')).toBeVisible()
  })
})
