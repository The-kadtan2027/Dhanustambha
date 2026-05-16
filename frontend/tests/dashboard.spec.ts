import { test, expect } from '@playwright/test';

test('has title containing Dhanustambha', async ({ page }) => {
  // Navigate to the dashboard root
  await page.goto('/');

  // Look for the main title element or body text
  await expect(page.locator('body')).toContainText(/Dhanustambha/i);
});

test('loads watchlist summary correctly', async ({ page }) => {
  // Navigate to dashboard
  await page.goto('/');

  // Verifying elements load without Next.js errors
  // Wait for at least one critical UI section
  await expect(page.locator('text=Market Monitor')).toBeVisible({ timeout: 10000 });
});
