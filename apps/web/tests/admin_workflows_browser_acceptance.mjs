/* UI-010D deterministic Administrator workflow browser acceptance suite. */
import { spawn } from 'node:child_process';
import { once } from 'node:events';

const scenarios = [
  'admin_bootstrap_browser_acceptance.mjs',
  'token_lifecycle_browser_acceptance.mjs',
  'admin_center_browser_acceptance.mjs',
  'admin_auth_browser_acceptance.mjs',
  'admin_backups_browser_acceptance.mjs',
  'admin_restore_browser_acceptance.mjs',
];

for (const scenario of scenarios) {
  const child = spawn(process.execPath, [`apps/web/tests/${scenario}`], {
    cwd: process.cwd(), env: process.env, stdio: 'inherit',
  });
  const [code] = await once(child, 'exit');
  if (code !== 0) throw new Error(`Administrator browser scenario failed: ${scenario}`);
}
console.log(`UI-010D Administrator workflow suite: OK (${scenarios.length} isolated scenarios)`);
