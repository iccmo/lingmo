import { test, expect } from '@playwright/test';

test.describe('听书流程 - UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => { sessionStorage.setItem('session', 'active'); });
  });
  test('听书大厅加载', async ({ page }) => {
    await page.goto('/listen');
    await page.waitForTimeout(2000);
    await expect(page.locator('text=共谋').first()).toBeVisible({ timeout: 5000 });
  });
  test('播放列表存在', async ({ page }) => {
    await page.goto('/listen');
    await page.waitForTimeout(2000);
    await expect(page.locator('text=播放列表').or(page.locator('text=清空')).first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('听书流程 - API', () => {
  test('TTS 端点正常', async ({ request }) => {
    expect((await request.get('/api/novels/gongmou/chapters/1/tts')).status()).toBe(200);
  });
  test('搜索端点正常', async ({ request }) => {
    expect((await request.get('/api/search?q=%E5%85%B1%E8%B0%8B')).status()).toBe(200);
  });
  test('音频数据端点', async ({ request }) => {
    expect((await request.get('/api/audio/data?novel_id=gongmou')).status()).toBe(200);
  });
  test('配音员列表', async ({ request }) => {
    expect((await request.get('/api/writer-voices')).status()).toBe(200);
  });
});
