import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => route.request().url().startsWith('http://127.0.0.1:8787/') ? route.continue() : route.abort());
});

test('actual browser sees all five protected outcomes and custom input', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Verify before release.' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Candidate response' })).toHaveValue(/Python.org/);
  const outcomes = [
    ['Supported claims', 'ALLOW', '200'], ['Older Python', 'REJECT', '403'],
    ['Extra assertion', 'UNAVAILABLE', '503'], ['Missing plugin', 'INGRESS_REFUSED', '503'],
    ['Provider failure', 'PROVIDER_ERROR', '400'],
  ];
  for (const [name, outcome, status] of outcomes) {
    await page.getByRole('button', { name: new RegExp(name) }).click();
    const candidate = await page.getByRole('textbox', { name: 'Candidate response' }).inputValue();
    const exchange = page.waitForResponse('/api/demo/verify');
    await page.getByRole('button', { name: 'Run verification' }).click();
    const response = await exchange;
    expect(response.status()).toBe(Number(status));
    await expect(page.locator('.outcome-code')).toContainText(outcome);
    await expect(page.locator('.outcome-code')).toContainText(`HTTP ${status}`);
    if (status === '200') await expect(page.getByTestId('released-content')).toHaveText(candidate);
    else {
      await expect(page.getByTestId('released-content')).toHaveCount(0);
      await expect(page.getByText('NO CANDIDATE CONTENT RELEASED')).toBeVisible();
    }
  }
  await page.getByRole('button', { name: /Supported claims/ }).click();
  await page.getByRole('textbox', { name: 'Candidate response' }).fill('PyPI reports requests version 2.34.2.');
  await page.getByRole('textbox', { name: 'Candidate response' }).press('Control+Enter');
  await expect(page.getByTestId('released-content')).toHaveText('PyPI reports requests version 2.34.2.');
  await page.getByRole('textbox', { name: 'Candidate response' }).fill('PyPI reports requests version 2.34.2. Extra unverified prose.');
  await expect(page.getByTestId('released-content')).toHaveCount(0);
  await page.getByRole('button', { name: 'Run verification' }).click();
  await expect(page.locator('.outcome-code')).toContainText('UNAVAILABLE');
  await expect(page.getByTestId('released-content')).toHaveCount(0);
  await page.getByRole('button', { name: /Supported claims/ }).click();
  await page.getByRole('button', { name: 'Run verification' }).click();
  await expect(page.getByTestId('released-content')).toBeVisible();
  await page.screenshot({ path: '../../artifacts/005a/lab-desktop.png', fullPage: true });
});

test('mobile layout, keyboard focus and grammar explanation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('textbox', { name: 'Candidate response' })).toHaveValue(/Python.org/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('button', { name: /Supported language/ }).click();
  await expect(page.getByText(/Exactly nine ASCII sentence forms/)).toBeVisible();
  await page.getByRole('button', { name: /Supported language/ }).click();
  await page.getByRole('button', { name: 'Run verification' }).click();
  await expect(page.getByTestId('released-content')).toBeVisible();
  await page.getByRole('tab', { name: 'Safe JSON record' }).click();
  await expect(page.getByRole('tabpanel')).toContainText('"evidence_mode": "fixture"');
  await page.screenshot({ path: '../../artifacts/005a/lab-mobile.png', fullPage: true });
});
