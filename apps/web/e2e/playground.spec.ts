import { expect, test } from '@playwright/test'

test('a team member can submit text and inspect the result', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your text').fill('We are building a working prototype for four teammates.')
  await page.getByRole('button', { name: 'Analyze text' }).click()
  await expect(page.getByRole('heading', { name: 'Summary', exact: true })).toBeVisible()
  await expect(page.getByText('Demo data · no AI model was called')).toBeVisible()
  await page.getByText('Run details').click()
  await expect(page.getByText('deterministic-mock-v1')).toBeVisible()
})

test('upstream failure is visible and a user can retry', async ({ page }) => {
  await page.route('**/api/analyze', route => route.fulfill({
    status: 504, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'model_timeout', request_id: 'timeout-test' } }),
  }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Analyze text' }).click()
  await expect(page.getByRole('alert')).toContainText('timeout-test')
  await expect(page.getByRole('button', { name: 'Analyze text' })).toBeEnabled()
})
