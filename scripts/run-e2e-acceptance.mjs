import { spawn } from 'node:child_process';
import { access, mkdtemp, rm } from 'node:fs/promises';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const backendRoot = join(repositoryRoot, 'apps', 'backend');
const frontendRoot = join(repositoryRoot, 'apps', 'frontend');
const runtimeRoot = await mkdtemp(join(tmpdir(), 'partha-e2e-acceptance-'));
const fixtureManifest = join(runtimeRoot, 'e2e-fixtures.json');

function availableLoopbackPort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.unref();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address === 'string') {
        server.close();
        reject(new Error('Could not allocate a disposable loopback port.'));
        return;
      }
      const { port } = address;
      server.close((error) => {
        if (error) reject(error);
        else resolvePort(port);
      });
    });
  });
}

const apiPort = process.env.PARTHA_E2E_API_PORT ?? await availableLoopbackPort();
const appPort = process.env.PARTHA_E2E_APP_PORT ?? await availableLoopbackPort();
const apiUrl = `http://127.0.0.1:${apiPort}`;
const appUrl = `http://127.0.0.1:${appPort}`;
const screenshotDirectory = process.env.PARTHA_VISUAL_SCREENSHOT_DIR
  ? resolve(repositoryRoot, process.env.PARTHA_VISUAL_SCREENSHOT_DIR)
  : undefined;
const children = [];
let shuttingDown = false;

async function pythonExecutable() {
  const virtualenvCandidates = process.platform === 'win32'
    ? [join(backendRoot, '.venv', 'Scripts', 'python.exe')]
    : [join(backendRoot, '.venv', 'bin', 'python')];
  for (const virtualenvPython of virtualenvCandidates) {
    try {
      await access(virtualenvPython);
      return virtualenvPython;
    } catch {
      // Try the next platform-appropriate candidate.
    }
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function start(command, args, options) {
  const child = spawn(command, args, { stdio: 'inherit', ...options });
  children.push(child);
  return child;
}

function waitForExit(child, label) {
  return new Promise((resolvePromise, reject) => {
    child.once('error', reject);
    child.once('exit', (code, signal) => {
      if (code === 0) resolvePromise();
      else reject(new Error(`${label} exited with ${code ?? signal}`));
    });
  });
}

async function waitForUrl(url, label) {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The process has not bound the port yet.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 250));
  }
  throw new Error(`${label} was not ready at ${url} within 90 seconds`);
}

async function stopChildren() {
  shuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
  }
  await Promise.all(
    children.map(
      (child) =>
        new Promise((resolvePromise) => {
          if (child.exitCode !== null || child.signalCode !== null) return resolvePromise();
          child.once('exit', resolvePromise);
          setTimeout(resolvePromise, 3000);
        }),
    ),
  );
}

let interrupted = false;
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, async () => {
    interrupted = true;
    await stopChildren();
    process.exitCode = 130;
  });
}

try {
  const python = await pythonExecutable();
  const backend = start(
    python,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(apiPort), '--log-level', 'warning'],
    {
      cwd: backendRoot,
      env: {
        ...process.env,
        APP_ENV: 'development',
        LOG_LEVEL: 'WARNING',
        DATABASE_URL: `sqlite:///${join(runtimeRoot, 'partha.db')}`,
        STORAGE_PATH: join(runtimeRoot, 'storage'),
        AUTO_CREATE_TABLES: 'true',
        RATE_LIMIT_ENABLED: 'false',
        ANALYSIS_JOB_POLL_INTERVAL_SECONDS: '1',
        CORS_ORIGINS: `${appUrl},http://localhost:5173`,
      },
    },
  );
  backend.once('exit', (code) => {
    if (!interrupted && !shuttingDown && code !== null && code !== 0) {
      process.stderr.write(`Backend stopped early (${code}).\n`);
    }
  });
  await waitForUrl(`${apiUrl}/ready`, 'backend');

  const frontend = start(
    process.execPath,
    [
      join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'),
      '--host',
      '127.0.0.1',
      '--port',
      String(appPort),
    ],
    {
      cwd: frontendRoot,
      env: { ...process.env, VITE_API_URL: apiUrl },
    },
  );
  frontend.once('exit', (code) => {
    if (!interrupted && !shuttingDown && code !== null && code !== 0) {
      process.stderr.write(`Frontend stopped early (${code}).\n`);
    }
  });
  await waitForUrl(appUrl, 'frontend');

  const seed = start(process.execPath, [join(repositoryRoot, 'scripts', 'seed-e2e-fixtures.mjs')], {
    cwd: repositoryRoot,
    env: {
      ...process.env,
      PARTHA_FIXTURE_API_URL: apiUrl,
      PARTHA_FIXTURE_PYTHON: python,
      // Registration requires an admin-approved email (#374): the seeder
      // shells out to apps/backend/scripts/approve_email.py to approve one,
      // which needs to resolve to the exact same database the backend above
      // is running against, not whatever DATABASE_URL defaults to locally.
      DATABASE_URL: `sqlite:///${join(runtimeRoot, 'partha.db')}`,
      PARTHA_VISUAL_FIXTURES: fixtureManifest,
    },
  });
  await waitForExit(seed, 'fixture seeder');

  const playwright = start(
    process.execPath,
    [
      join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js'),
      'test',
      ...process.argv.slice(2),
    ],
    {
      cwd: frontendRoot,
      env: {
        ...process.env,
        PARTHA_E2E_BASE_URL: appUrl,
        PARTHA_VISUAL_FIXTURES: fixtureManifest,
        // surfaces.spec.ts registers a second owner directly (#374 requires
        // an approved email for that too) and approves one the same way the
        // fixture seeder does, against this same runtime database.
        PARTHA_FIXTURE_PYTHON: python,
        DATABASE_URL: `sqlite:///${join(runtimeRoot, 'partha.db')}`,
        ...(screenshotDirectory
          ? { PARTHA_VISUAL_SCREENSHOT_DIR: screenshotDirectory }
          : {}),
      },
    },
  );
  await waitForExit(playwright, 'browser acceptance');
} finally {
  await stopChildren();
  if (process.env.PARTHA_E2E_KEEP_TEMP !== '1') {
    await rm(runtimeRoot, { recursive: true, force: true });
  } else {
    process.stdout.write(`Kept e2e acceptance runtime: ${runtimeRoot}\n`);
  }
}
