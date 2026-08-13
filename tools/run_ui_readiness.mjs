import { spawn } from 'node:child_process';
import { access, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, join, resolve } from 'node:path';
import { UI_READINESS_SUITES } from '../apps/web/tests/ui_readiness_manifest.mjs';

const root = process.cwd();
const artifactRoot = await mkdtemp(join(tmpdir(), 'curator-ui-readiness-'));
const results = [];
let activeChild = null;

function sanitized(value) {
  return String(value)
    .replace(/Bearer\s+[^\s"']+/gi, 'Bearer [REDACTED]')
    .replace(/((?:device|admin|bootstrap)[_-]?token\s*[:=]\s*)[^\s"']+/gi, '$1[REDACTED]')
    .replace(/[A-Za-z0-9_-]{40,}\.[a-f0-9]{32,}/gi, '[REDACTED_SIGNED_TOKEN]');
}

async function preflight() {
  if (Number(process.versions.node.split('.')[0]) < 20) throw new Error('Node.js 20 or newer is required.');
  await access(resolve('node_modules', 'playwright', 'package.json'));
  const requiredDimensions=['modalClose','navigation','refresh','browserRestart','backendRestart','delayedAction','retry','cancellation','upgradeCache'];
  for (const suite of UI_READINESS_SUITES) {
    await access(resolve(suite.args.at(-1)));
    for(const dimension of requiredDimensions){
      const claim=suite.interruptions?.[dimension];
      if(!claim||!(/^(covered|not-applicable): /.test(claim)))throw new Error(`${suite.id} lacks a reasoned ${dimension} interruption claim.`);
    }
  }
}

function runSuite(suite) {
  return new Promise((accept) => {
    const started = Date.now();
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const child = spawn(suite.command, suite.args, {
      cwd: root,
      env: { ...process.env, CURATOR_UI_GATE_ARTIFACT_DIR: artifactRoot },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    activeChild = child;
    child.stdout.on('data', chunk => { const value = String(chunk); stdout += value; process.stdout.write(value); });
    child.stderr.on('data', chunk => { const value = String(chunk); stderr += value; process.stderr.write(value); });
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGTERM'); }, suite.timeoutMs);
    child.once('error', error => {
      clearTimeout(timer);
      activeChild = null;
      accept({ ok: false, timedOut, durationMs: Date.now() - started, stdout, stderr: `${stderr}\n${error.stack || error}` });
    });
    child.once('exit', (code, signal) => {
      clearTimeout(timer);
      activeChild = null;
      accept({ ok: code === 0 && !timedOut, code, signal, timedOut, durationMs: Date.now() - started, stdout, stderr });
    });
  });
}

function stopActive() { activeChild?.kill('SIGTERM'); }
process.once('SIGINT', stopActive);
process.once('SIGTERM', stopActive);

try {
  await preflight();
  console.log(`UI readiness gate: ${UI_READINESS_SUITES.length} required suites`);
  for (const suite of UI_READINESS_SUITES) {
    console.log(`\n[RUN] ${suite.id} · ${suite.task}`);
    const outcome = await runSuite(suite);
    results.push({ suite, ...outcome });
    if (!outcome.ok) {
      const artifact = join(artifactRoot, `${suite.id}-failure.txt`);
      await writeFile(artifact, sanitized([
        `suite=${suite.id}`, `task=${suite.task}`, `specification=${suite.specification}`,
        `backend_evidence=${suite.backendEvidence}`, `timeout=${outcome.timedOut}`,
        '', outcome.stdout, outcome.stderr,
      ].join('\n')), 'utf8');
      console.error(`[FAIL] ${suite.id} · sanitized artifact: ${artifact}`);
      continue;
    }
    console.log(`[PASS] ${suite.id} · ${(outcome.durationMs / 1000).toFixed(1)}s`);
  }

  console.log('\nUI readiness summary');
  for (const { suite, ok, durationMs, timedOut } of results) {
    console.log(`${ok ? 'PASS' : 'FAIL'}\t${suite.id}\t${suite.task}\t${(durationMs / 1000).toFixed(1)}s${timedOut ? '\tTIMEOUT' : ''}`);
    console.log(`  specification: ${suite.specification}`);
    console.log(`  backend evidence: ${suite.backendEvidence}`);
    console.log(`  interruptions: ${Object.entries(suite.interruptions).map(([key,value])=>`${key}=${value}`).join('; ')}`);
  }
  if (results.length !== UI_READINESS_SUITES.length || results.some(result => !result.ok)) {
    process.exitCode = 1;
  } else {
    await rm(artifactRoot, { recursive: true, force: true });
    console.log(`All required UI readiness suites passed; removed ${basename(artifactRoot)}.`);
  }
} catch (error) {
  const artifact = join(artifactRoot, 'gate-preflight-failure.txt');
  await writeFile(artifact, sanitized(error.stack || error), 'utf8');
  console.error(`UI readiness preflight failed. Sanitized artifact: ${artifact}`);
  process.exitCode = 1;
}
