import { defineConfig, devices } from '@playwright/test';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';

const allBrowsers = process.env.CURATOR_E2E_ALL_BROWSERS === '1';
const outputDir = process.env.CURATOR_PLAYWRIGHT_OUTPUT_DIR
  || resolve(tmpdir(), 'curator-playwright-results');

export default defineConfig({
  testDir: './apps/web/e2e',
  outputDir,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    ...(allBrowsers ? [
      { name: 'webkit', use: { ...devices['Desktop Safari'] } },
      { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    ] : []),
  ],
});
