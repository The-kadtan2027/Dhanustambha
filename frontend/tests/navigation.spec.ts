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
  await expect(page.locator('h1')).toContainText(/Trade Book/);

  // Navigate to Journal
  await page.getByRole('link', { name: 'Journal' }).click();
  await expect(page).toHaveURL(/.*journal/);
  await expect(page.locator('h1')).toContainText(/Review Journal/i);
});

test('scanner execute ticket requests a backend quote', async ({ page }) => {
  await page.goto('/scanners');

  await page.locator('select').selectOption('2026-05-11');
  await expect(page.getByText('5 candidates found')).toBeVisible({ timeout: 10000 });

  await page.getByRole('link', { name: 'AFFLE' }).click();
  await page.getByRole('button', { name: 'Execute' }).click();

  await expect(page.getByText('OFFENSIVE')).toBeVisible({ timeout: 10000 });
  await expect(page.getByText('Computed Shares').locator('..')).not.toContainText('-');
  await expect(page.getByRole('button', { name: 'Confirm Trade' })).toBeEnabled();
});

test('trade book shows card grid by default', async ({ page }) => {
  await page.goto('/trades');
  await expect(page.locator('.timeframeBtn').first()).toBeVisible();
  await expect(page.locator('h1')).toContainText(/Trade Book/i);
});

test('stock detail route loads for a symbol', async ({ page }) => {
  await page.goto('/stock/RELIANCE');
  await expect(page.locator('h1')).toContainText('RELIANCE');
  await expect(page.getByRole('button', { name: /back/i })).toBeVisible();
});

test('market monitor has a dedicated breadth page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Market Monitor' }).click();

  await expect(page).toHaveURL(/.*market/);
  await expect(page.locator('h1')).toContainText(/Market Monitor/i);
  await expect(page.getByRole('button', { name: '3M' })).toBeVisible();
  await expect(page.getByText('Daily Advances - Declines')).toBeVisible();
});
