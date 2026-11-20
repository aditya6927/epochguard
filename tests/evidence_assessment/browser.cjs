// Optional UI qualification using the existing Lab Playwright installation.
// Start the OFFLINE Explorer first. No external browser requests are permitted.
const { chromium, expect } = require('../../web/lab/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const output = process.argv[2];
  if (!output || fs.existsSync(output)) throw new Error('new output directory required');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true,
    args: ['--disable-background-networking', '--disable-component-update', '--no-first-run'] });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
    await page.route('**/*', r => r.request().url().startsWith('http://127.0.0.1:8791/') ? r.continue() : r.abort());
    await page.goto('http://127.0.0.1:8791/');
    await expect(page.locator('#mode')).toContainText('SIMULATED'); // Refuse any live service.
    await expect(page.getByText('AI-assisted assessment — not gateway authorization', { exact: true })).toBeVisible();
    const rows = [];
    for (const [button, assessment] of [[null, 'CONTRADICTED'], ['stable', 'SUPPORTED'], ['unclear', 'INSUFFICIENT_EVIDENCE']]) {
      if (button) await page.locator('#' + button).click();
      const claim = await page.locator('#claim').inputValue();
      const exchange = page.waitForResponse('http://127.0.0.1:8791/api/assess');
      await page.locator('#run').click();
      const response = await exchange;
      const value = await response.json();
      expect(value.claim).toBe(claim);
      expect(value.authorization).toBe(false);
      expect(value.evidence_mode).toBe('simulated');
      await expect(page.locator('#assessment')).toHaveText('AI-assessed ' + assessment);
      await expect(page.locator('#result')).toBeVisible();
      expect(await page.locator('#sources a').evaluateAll(links => links.every(a => a.href.startsWith('https:') && a.rel.includes('noopener')))).toBe(true);
      rows.push({ assessment, status: response.status(), authorization: false, sources: value.sources.length });
    }
    await page.locator('#claim').fill('An edited claim must clear the previous result.');
    await expect(page.locator('#result')).toBeHidden();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({ simulated: true, cases: rows, edit_clears_result: true, mobile_no_overflow: true }, null, 2) + '\n');
    console.log('3/3 actual browser outcomes; stale-result and mobile checks passed.');
  } finally { await browser.close(); }
})().catch(() => { console.error('Offline browser qualification failed; no raw response printed.'); process.exitCode = 1; });
