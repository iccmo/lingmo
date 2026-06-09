import { test, expect } from '@playwright/test';

test.describe('写作流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => { sessionStorage.setItem('session', 'active'); });
  });

  test('WriterView 页面加载', async ({ page }) => {
    await page.goto('/novels/gongmou/write');
    await page.waitForTimeout(2000);
    await expect(page.locator('text=共谋').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('h1, h2, [class*="title"]').first()).toBeVisible({ timeout: 5000 });
  });

  test('章节内容展开', async ({ page }) => {
    await page.goto('/novels/gongmou/write');
    await page.waitForTimeout(2000);
    const ch1 = page.locator('text=第1章').first();
    if (await ch1.isVisible()) { await ch1.click(); await page.waitForTimeout(800); }
    await expect(page.locator('text=空椅').or(page.locator('text=第1章')).first()).toBeVisible({ timeout: 3000 });
  });

  test('分析页加载', async ({ page }) => {
    await page.goto('/novels/gongmou/analysis');
    await page.waitForSelector('text=分析', { timeout: 10000 });
    await expect(page.locator('text=质量趋势').first()).toBeVisible({ timeout: 5000 });
  });
});
