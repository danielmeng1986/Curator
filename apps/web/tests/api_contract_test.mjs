import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../static/api.js', import.meta.url), 'utf8');
const stored = new Map();
let calls = [];
let nextResponse = { ok: true, status: 200, json: async () => ({ data: { statuses: [] }, meta: {} }) };
const window = {
  CURATOR_WEB_CONFIG: {},
  localStorage: {
    getItem: (key) => stored.get(key) || null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: (key) => stored.delete(key),
  },
};
const context = vm.createContext({ window, fetch: async (...args) => { calls.push(args); return nextResponse; } });
vm.runInContext(source, context, { filename: 'api.js' });
const { api } = window;

await assert.rejects(api.get('/statuses'), (error) => error.code === 'AUTHENTICATION_MISSING_TOKEN');
assert.equal(calls.length, 0, 'missing token must prevent a request');

api.configure({ backendUrl: 'http://127.0.0.1:8788/', token: 'approved-token' });
nextResponse = {
  ok: true,
  status: 200,
  json: async () => ({ data: [{ id: 1, name: 'Example' }], meta: { total: 1 } }),
};
assert.equal(
  JSON.stringify(await api.get('/albums?limit=1')),
  JSON.stringify({ albums: [{ id: 1, name: 'Example' }], total: 1 }),
);
assert.equal(calls[0][0], 'http://127.0.0.1:8788/api/v1/albums?limit=1');
assert.equal(calls[0][1].headers.Authorization, 'Bearer approved-token');

nextResponse = {
  ok: false,
  status: 401,
  json: async () => ({ error: { code: 'AUTHENTICATION_REVOKED_TOKEN', message: 'Token is revoked.' } }),
};
await assert.rejects(api.get('/statuses'), (error) => error.code === 'AUTHENTICATION_REVOKED_TOKEN' && api.isAuthenticationError(error));

nextResponse = {
  ok: false,
  status: 403,
  json: async () => ({ error: { code: 'AUTHORIZATION_INSUFFICIENT_SCOPE', message: 'Admin required.' } }),
};
await assert.rejects(api.post('/backup', {}), (error) => (
  !api.isAuthenticationError(error) && api.isAuthorizationError(error)
));

let releaseMutation;
const pendingMutation = new Promise((resolve) => { releaseMutation = resolve; });
context.fetch = async (...args) => {
  calls.push(args);
  await pendingMutation;
  return { ok: true, status: 200, json: async () => ({ data: { id: 2 }, meta: {} }) };
};
const firstMutation = api.post('/albums', { title: 'One' });
await assert.rejects(api.post('/albums', { title: 'One' }), (error) => api.isActionInProgressError(error));
releaseMutation();
await firstMutation;

assert.equal(new api.Error('X', 'x', 409, { requestId: 'req-1' }).requestId, 'req-1');

assert.ok(!source.includes("fetch('/api'"), 'client must not call a pre-versioned API base');
console.log('apps/web API contract: OK');
