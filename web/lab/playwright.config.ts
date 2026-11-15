import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './browser', workers: 1, fullyParallel: false, timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:8787', browserName: 'chromium', channel: 'msedge',
    headless: process.env.EPOCHGUARD_LAB_HEADED !== '1', trace: 'off',
    launchOptions: { args: ['--disable-background-networking', '--disable-component-update', '--no-first-run'] } },
});
