import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../static/ui.js', import.meta.url), 'utf8');
const context = vm.createContext({
  window: { api: { Error: class extends Error { constructor(code, message, status = 0) { super(message); this.code = code; this.status = status; } } } },
  document: { getElementById: () => null },
  setTimeout,
});
vm.runInContext(source, context, { filename: 'ui.js' });
const { ui } = context.window;

assert.equal(ui.errorPresentation({ code: 'AUTHENTICATION_REVOKED_TOKEN', status: 401 }).kind, 'authentication');
assert.equal(ui.errorPresentation({ code: 'AUTHORIZATION_INSUFFICIENT_SCOPE', status: 403 }).kind, 'authorization');
assert.equal(ui.errorPresentation({ code: 'REQUEST_INVALID', status: 400, message: 'Title is required.' }).kind, 'validation');
assert.equal(ui.errorPresentation({ code: 'NEEDS_REPAIR', status: 409 }).title, 'Repair review required');
assert.equal(ui.errorPresentation({ code: 'NETWORK_UNAVAILABLE' }).kind, 'network');
assert.equal(ui.errorPresentation({ code: 'AUTHENTICATION_BOOTSTRAP_CODE_LOCKED', message: 'The Bootstrap Code is locked.' }).kind, 'validation');
assert.equal(ui.errorPresentation({ code: 'INTERNAL_ERROR', message: '<private path>' }).message.includes('private path'), false);
assert.equal(ui.errorHtml({ code: 'REQUEST_INVALID', status: 400, message: '<bad>' }).includes('&lt;bad&gt;'), true);

assert.equal(ui.can('reader', 'read'), true);
assert.equal(ui.can('reader', 'write'), false);
assert.equal(ui.can('writer', 'admin'), false);
assert.equal(ui.can('admin', 'admin'), true);

let calls = 0;
let release;
const pending = new Promise((resolve) => { release = resolve; });
const first = ui.runAction('save-album', async () => { calls += 1; await pending; return 42; });
const second = await ui.runAction('save-album', async () => { calls += 1; });
assert.equal(second.ok, false);
assert.equal(second.error.code, 'CLIENT_ACTION_IN_PROGRESS');
assert.equal(calls, 1);
release();
assert.equal((await first).value, 42);

console.log('apps/web UI interaction contract: OK');
