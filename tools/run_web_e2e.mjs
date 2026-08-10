import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const artifactRoot = await mkdtemp(join(tmpdir(), 'curator-playwright-'));
const executable = resolve('node_modules', '.bin', process.platform === 'win32' ? 'playwright.cmd' : 'playwright');
const child = spawn(executable, ['test', ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env: { ...process.env, CURATOR_PLAYWRIGHT_OUTPUT_DIR: artifactRoot },
  stdio: 'inherit',
});

const code = await new Promise((accept, reject) => {
  child.once('error', reject);
  child.once('exit', (exitCode, signal) => accept(signal ? 1 : (exitCode ?? 1)));
});

if (code === 0) {
  await rm(artifactRoot, { recursive: true, force: true });
} else {
  console.error(`Playwright failure artifacts: ${artifactRoot}`);
}
process.exitCode = code;
