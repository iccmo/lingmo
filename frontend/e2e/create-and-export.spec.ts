import { test, expect } from '@playwright/test';

test.describe('创建 → 导出', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem('session', 'active');
    });
  });

  test('Dashboard 工作台加载', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
    await expect(page.locator('text=共谋').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=工作台').first()).toBeVisible({ timeout: 5000 });
  });

  test('共谋详情页', async ({ page }) => {
    await page.goto('/novels/gongmou');
    await page.waitForSelector('h1', { timeout: 10000 });
    await expect(page.locator('h1')).toContainText('共谋');
    await expect(page.locator('text=章节数')).toBeVisible();
    await expect(page.locator('text=总字数')).toBeVisible();
    await expect(page.locator('text=角色管理')).toBeVisible();
  });
});
