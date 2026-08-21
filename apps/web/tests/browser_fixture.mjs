/* Shared disposable scenario builder for Curator browser workflow tests. */
import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { access, mkdir, writeFile } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import { resolve, sep } from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

export const SCENARIOS = Object.freeze({
  empty: Object.freeze({ readiness: 'Ready' }),
  entities: Object.freeze({ readiness: 'Ready' }),
  'workflow-evidence': Object.freeze({ readiness: 'Ready' }),
  filesystem: Object.freeze({ readiness: 'Ready' }),
  'future-ai-workspace': Object.freeze({
    readiness: 'Ready',
    dependency: 'BT-053/BT-058 and UI-011E',
  }),
  'work-dispatch-pagination': Object.freeze({
    readiness: 'Ready',
    dependency: 'BT-055 and UI-032',
  }),
  'digital-asset-trash': Object.freeze({ readiness: 'Ready', dependency: 'BT-034 and UI-037' }),
});

const ROLE_SCOPES = Object.freeze({
  reader: ['read'],
  writer: ['read', 'write'],
  admin: ['read', 'write', 'admin'],
});

function isUnder(root, candidate) {
  const normalizedRoot = resolve(root);
  const normalizedCandidate = resolve(candidate);
  return normalizedCandidate === normalizedRoot || normalizedCandidate.startsWith(`${normalizedRoot}${sep}`);
}

async function post(origin, path, body, token = '') {
  const response = await fetch(`${origin}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(`${response.status} ${payload.error?.code || 'REQUEST_FAILED'}`);
  return payload.data;
}

async function issueDevice(origin, secret, fixtureId, role, index, adminToken) {
  if (!ROLE_SCOPES[role]) throw new Error(`Unsupported fixture role: ${role}`);
  const registration = await post(origin, '/api/auth/registrations', {
    device_name: `Browser fixture ${role}`,
    device_identity: `${fixtureId}-${role}-${index}`,
    requested_role: role,
    requested_scopes: ROLE_SCOPES[role],
    registration_proof: secret,
  });
  const issued = await post(
    origin, `/api/v1/auth/registrations/${registration.registration.uuid}/approve`, {}, adminToken,
  );
  return Object.freeze({
    token: issued.token,
    tokenRecord: issued.token_record,
    registration: registration.registration,
    role,
  });
}

export async function createBootstrapCode(databasePath) {
  const { stdout } = await execFileAsync('python3', [
    '-m', 'apps.backend', 'auth', 'create-bootstrap-code', '--database', databasePath,
  ], { cwd: process.cwd() });
  const lines = stdout.split(/\r?\n/);
  return lines[lines.indexOf('Administrator UI Bootstrap Code (shown once; valid for 10 minutes):') + 1];
}

export async function setFixtureTokenState(databasePath, tokenUuid, state) {
  await execFileAsync('python3', [
    'apps/web/tests/fixture_token_state.py', '--database', databasePath,
    '--token-uuid', tokenUuid, '--state', state,
  ], { cwd: process.cwd() });
}

async function bootstrapFixtureAdmin(databasePath) {
  const { stdout } = await execFileAsync('python3', [
    '-m', 'apps.backend', 'auth', 'bootstrap-admin',
    '--device-name', 'Fixture Administrator', '--device-identity', `fixture-admin-${randomBytes(8).toString('hex')}`,
    '--database', databasePath,
  ], { cwd: process.cwd() });
  const lines = stdout.split(/\r?\n/);
  return lines[lines.indexOf('Admin Token (shown once):') + 1];
}

export async function startBrowserFixture({ scenario = 'empty', roles = ['writer'], artifactDir = null, bootstrapAdmin = true, pendingRegistrations = [] } = {}) {
  const metadata = SCENARIOS[scenario];
  if (!metadata) throw new Error(`Unknown browser fixture scenario: ${scenario}`);
  if (metadata.readiness !== 'Ready') {
    throw new Error(`${scenario} is ${metadata.readiness}; complete ${metadata.dependency} first.`);
  }

  const secret = randomBytes(24).toString('base64url');
  const child = spawn('python3', [
    'apps/web/tests/disposable_backend.py', `--secret=${secret}`, '--scenario', scenario,
  ], { cwd: process.cwd(), stdio: ['ignore', 'pipe', 'pipe'] });
  let stderr = '';
  child.stderr.on('data', (data) => { stderr += String(data); });
  const lines = createInterface({ input: child.stdout });
  const linePromise = once(lines, 'line').then(([line]) => line);
  const earlyExit = once(child, 'exit').then(([code]) => { throw new Error(`Fixture Backend exited ${code}: ${stderr}`); });
  const manifest = JSON.parse(await Promise.race([linePromise, earlyExit]));
  lines.close();

  assert.equal(manifest.scenario, scenario);
  assert.match(manifest.root, /curator-browser-/);
  for (const path of Object.values(manifest.resources)) {
    assert.equal(isUnder(manifest.root, path), true, `Fixture resource escaped root: ${path}`);
  }
  const repoRuntime = resolve('var');
  assert.equal(isUnder(repoRuntime, manifest.root), false, 'fixture root must not use repository runtime');

  const devices = {};
  const fixtureAdminToken = bootstrapAdmin ? await bootstrapFixtureAdmin(manifest.resources.database) : null;
  if (!bootstrapAdmin && roles.length) throw new Error('roles require bootstrapAdmin in the secured fixture.');
  for (const [index, role] of roles.entries()) {
    if (role === 'admin') {
      devices.admin = Object.freeze({ token: fixtureAdminToken, role: 'admin' });
    } else {
      devices[role] = await issueDevice(manifest.origin, secret, manifest.fixture_id, role, index, fixtureAdminToken);
    }
  }
  const pending = [];
  for (const [index, request] of pendingRegistrations.entries()) {
    pending.push(await post(manifest.origin, '/api/auth/registrations', {
      device_name: request.device_name || `Pending fixture ${index + 1}`,
      device_identity: request.device_identity || `${manifest.fixture_id}-pending-${index}`,
      requested_role: request.requested_role || 'writer',
      requested_scopes: request.requested_scopes || ROLE_SCOPES[request.requested_role || 'writer'],
      registration_proof: secret,
    }));
  }
  const secrets = [secret, fixtureAdminToken, ...Object.values(devices).map((device) => device.token)].filter(Boolean);

  return Object.freeze({
    ...manifest,
    devices: Object.freeze(devices),
    pendingRegistrations: Object.freeze(pending),
    async request(path, { method = 'GET', body = undefined, role = roles[0] } = {}) {
      const token = devices[role]?.token;
      if (!token) throw new Error(`No ${role} device in this fixture.`);
      const response = await fetch(`${manifest.origin}/api/v1${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const payload = await response.json();
      return { status: response.status, payload };
    },
    sanitize(value) {
      return secrets.reduce((text, item) => text.replaceAll(item, '[REDACTED]'), String(value));
    },
    async writeFailureArtifact(name, value) {
      if (!artifactDir) throw new Error('An explicit disposable artifactDir is required.');
      const safeName = name.replace(/[^a-zA-Z0-9_.-]/g, '_');
      await mkdir(artifactDir, { recursive: true });
      const path = resolve(artifactDir, safeName);
      if (!isUnder(artifactDir, path)) throw new Error('Artifact path escaped its root.');
      await writeFile(path, this.sanitize(value), 'utf8');
      return path;
    },
    async stop() {
      child.kill('SIGTERM');
      await once(child, 'exit');
      await assert.rejects(access(manifest.root), 'fixture root must be removed after shutdown');
    },
  });
}
