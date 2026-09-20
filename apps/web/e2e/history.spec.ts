import { expect, test } from '@playwright/test'

test.skip(!process.env.PLAYWRIGHT_BASE_URL, 'Workflow history requires the Compose development lab')

test('a workflow can be run, inspected and loaded again from history', async ({ page }) => {
  await page.goto('/')
  const panel = page.getByRole('region', { name: 'Workflow history', exact: true })
  await expect(panel).toBeVisible()
  await panel.getByRole('button', { name: 'Run workflow', exact: true }).click()
  const detail = page.getByRole('region', { name: 'Workflow run details', exact: true })
  await expect(detail.locator('dd[data-status="completed"]')).toBeVisible()
  await expect(detail.getByRole('row')).toHaveCount(6)
  await expect(detail.getByText('accepted', { exact: true })).toBeVisible()
  const id = await detail.locator('dd code').textContent()
  expect(id).toBeTruthy()
  await page.reload()
  await page.getByRole('button', { name: `View run ${id}` }).click()
  await expect(detail.locator('dd[data-status="completed"]')).toBeVisible()
  await expect(detail.getByRole('cell', { name: '0 / 0', exact: true })).toBeVisible()
})

test('failed validation is visible and skipped nodes are distinguished', async ({ page, request }) => {
  const response = await request.post('/api/lab/workflow', { data: { text: ' ' } })
  expect(response.status()).toBe(422)
  const id = (await response.json()).error.request_id
  await page.goto('/')
  await page.getByRole('button', { name: `View run ${id}` }).click()
  const detail = page.getByRole('region', { name: 'Workflow run details', exact: true })
  await expect(detail.locator('dd[data-status="failed"]')).toBeVisible()
  await expect(detail.getByRole('cell', { name: 'skipped', exact: true })).toHaveCount(4)
  await expect(detail.getByRole('cell', { name: 'invalid_input', exact: true })).toBeVisible()
})

test('history excludes source text and fits a mobile viewport', async ({ page, request }) => {
  const marker = `source-private-${Date.now()}`
  const response = await request.post('/api/lab/workflow', {
    data: { text: `## 일정\nFriday\n## 준비\nSlides\n${marker}` },
  })
  expect(response.ok()).toBeTruthy()
  const id = (await response.json()).analysis.request_id
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: `View run ${id}` }).click()
  const detail = page.getByRole('region', { name: 'Workflow run details', exact: true })
  await expect(detail.locator('dd[data-status="completed"]')).toBeVisible()
  await expect(page.getByText(marker, { exact: false })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
})

test('history read failure can be retried', async ({ page }) => {
  await page.route('**/api/lab/runs?limit=20', route => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'database_unavailable' } }),
  }))
  await page.goto('/')
  const panel = page.getByRole('region', { name: 'Workflow history', exact: true })
  await expect(panel.getByRole('alert')).toContainText('database_unavailable')
  await page.unroute('**/api/lab/runs?limit=20')
  await panel.getByRole('button', { name: 'Refresh history' }).click()
  await expect(panel.getByRole('alert')).toHaveCount(0)
})
