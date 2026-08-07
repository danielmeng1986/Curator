/* Browser acceptance gate: only disposable Backend state is used. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const secret = 'ui-acceptance-secret';
const child = spawn('python3', ['apps/web/tests/disposable_backend.py', '--secret', secret], { cwd: process.cwd(), stdio: ['ignore', 'pipe', 'inherit'] });
const port = await new Promise((resolve, reject) => {
  child.stdout.once('data', data => resolve(Number(String(data).trim())));
  child.once('error', reject);
});
const origin = `http://127.0.0.1:${port}`;
try {
  const request = async (path, body = {}) => (await fetch(`${origin}${path}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) })).json();
  const registration = await request('/api/auth/registrations', { device_name:'Browser acceptance', device_identity:'browser-acceptance', requested_role:'writer', requested_scopes:['read','write'], registration_proof:secret });
  const approved = await request(`/api/auth/registrations/${registration.data.registration.uuid}/approve`);
  const token = approved.data.token;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(origin);
  await page.getByText('Authorization required').waitFor();
  await page.getByRole('button', { name:'Connect' }).click();
  await page.getByPlaceholder('Same origin when empty').fill(origin);
  await page.getByPlaceholder('Required').fill(token);
  await page.getByRole('button', { name:'Save' }).click();
  await page.getByText(/DB OK/).waitFor();
  await page.getByRole('link', { name:/Albums/ }).click();
  await page.getByRole('heading', { name:'Albums' }).waitFor();
  const before = (await (await fetch(`${origin}/api/v1/albums`, { headers:{Authorization:`Bearer ${token}`} })).json()).data.length;
  const denied = await fetch(`${origin}/api/v1/backup`, { method:'POST', headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'}, body:'{}' });
  assert.equal(denied.status, 403);
  const after = (await (await fetch(`${origin}/api/v1/albums`, { headers:{Authorization:`Bearer ${token}`} })).json()).data.length;
  assert.equal(after, before, 'rejected administrative action has no business side effect');
  await browser.close();
  console.log('browser workflow acceptance: ok');
} finally {
  child.kill('SIGTERM');
  await once(child, 'exit');
}
