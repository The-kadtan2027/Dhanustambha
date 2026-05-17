import { test, expect } from '@playwright/test';

test('has title containing Dhanustambha', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('body')).toContainText(/Dhanustambha/i);
});

test('loads watchlist summary correctly', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Market Monitor')).toBeVisible({ timeout: 10000 });
});

test('has sidebar navigation across all routes', async ({ page }) => {
  // Navigate to the dashboard root
  await page.goto('/');

  // Assert navigation sidebar is present
  const sidebar = page.locator('aside.sidebar');
  await expect(sidebar).toBeVisible();

  // Navigate to Scanners
  await page.getByRole('link', { name: 'Scanners' }).click();
  await expect(page).toHaveURL(/.*scanners/);
  await expect(page.locator('h1')).toContainText(/Scanners/i);

  // Navigate to Trade Book
  await page.getByRole('link', { name: 'Trade Book' }).click();
  await expect(page).toHaveURL(/.*trades/);
  await expect(page.locator('text=Open Trades')).toBeVisible();

  // Navigate to Journal
  await page.getByRole('link', { name: 'Journal' }).click();
  await expect(page).toHaveURL(/.*journal/);
  await expect(page.locator('h1')).toContainText(/Review Journal/i);
});
