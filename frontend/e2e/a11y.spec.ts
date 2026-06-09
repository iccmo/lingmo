import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function scan(page: any, name: string, maxViolations = 10) {
  const results = await new AxeBuilder({ page }).analyze();
  const violations = results.violations.filter(
    (v: any) => v.impact === 'critical' || v.impact === 'serious'
  );
  if (violations.length > 0) {
    console.log(`\n=== [a11y] ${name}: ${violations.length} violations ===`);
    for (const v of violations) {
      console.log(`  [${v.impact}] ${v.help} — ${v.nodes.length} element(s)`);
      for (const n of v.nodes.slice(0, 2)) {
        console.log(`    ${n.html?.slice(0, 60)}`);
      }
    }
  }
  expect(violations.length, `${name}: ${violations.length} a11y issues`).toBeLessThanOrEqual(maxViolations);
}

test.describe('A11y', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem('session', 'active'));
  });

  test('Dashboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
    await scan(page, 'Dashboard', 20);
  });

  test('Writer', async ({ page }) => {
    await page.goto('/novels/gongmou/write');
    await page.waitForTimeout(2000);
    await scan(page, 'Writer', 30);
  });

  test('Listen', async ({ page }) => {
    await page.goto('/listen');
    await page.waitForTimeout(2000);
    await scan(page, 'Listen', 15);
  });

  test('Settings', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForTimeout(2000);
    await scan(page, 'Settings', 30);
  });
});
