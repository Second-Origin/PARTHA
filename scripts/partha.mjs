import { spawn, spawnSync } from 'node:child_process';

const API_READY_URL = 'http://localhost:8000/ready';
const FRONTEND_URL = 'http://localhost:5173';
const REQUIREMENT_MESSAGE =
  'Docker Engine with Compose plugin is required; install Docker Desktop or docker-ce + plugin.';

let activeChild = null;
let cleanupPromise = null;
let interrupted = false;
let startupAttempted = false;
let releaseKeepAlive;

function commandOutput(result) {
  return [result.stdout, result.stderr]
    .filter(Boolean)
    .join('\n')
    .trim();
}

function requireDockerCapability(label, args) {
  const result = spawnSync('docker', args, {
    encoding: 'utf8',
    shell: false,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  if (result.error || result.status !== 0) {
    const detail =
      result.error?.message || commandOutput(result) || `docker ${args.join(' ')} failed`;
    throw new Error(`${label}: ${detail}`);
  }
}

function preflightDocker() {
  requireDockerCapability('Docker CLI is unavailable', ['--version']);
  requireDockerCapability('Docker Compose plugin is unavailable', ['compose', 'version']);
  requireDockerCapability('Docker buildx plugin is unavailable', ['buildx', 'version']);
  requireDockerCapability('Docker Engine is unavailable', ['info']);
}

function run(command, args, { allowFailure = false, stdio = 'inherit' } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { shell: false, stdio });
    activeChild = child;

    child.once('error', (error) => {
      if (activeChild === child) activeChild = null;
      reject(error);
    });
    child.once('exit', (code, signal) => {
      if (activeChild === child) activeChild = null;
      if (code === 0 || allowFailure) {
        resolve({ code, signal });
        return;
      }
      reject(new Error(`${command} ${args.join(' ')} exited with ${code ?? signal}`));
    });
  });
}

async function waitForUrl(url, label) {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (interrupted) throw new Error(`${label} readiness wait was interrupted`);
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
      if (response.ok) return;
    } catch {
      // The service is still starting.
    }
    if (interrupted) throw new Error(`${label} readiness wait was interrupted`);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`${label} did not become reachable at ${url} within 90 seconds`);
}

function showDiagnostics() {
  spawnSync('docker', ['compose', 'ps', '--all'], { shell: false, stdio: 'inherit' });
  spawnSync('docker', ['compose', 'logs', '--no-color', '--tail', '100'], {
    shell: false,
    stdio: 'inherit',
  });
}

async function stopActiveChild() {
  const child = activeChild;
  if (!child || child.exitCode !== null || child.signalCode !== null) return;

  const exited = new Promise((resolve) => child.once('exit', resolve));
  child.kill('SIGTERM');
  await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 3000))]);
}

function composeDown() {
  if (!cleanupPromise) {
    cleanupPromise = (async () => {
      await stopActiveChild();
      await run('docker', ['compose', 'down'], { allowFailure: true });
    })();
  }
  return cleanupPromise;
}

async function handleSignal(signal) {
  if (interrupted) return;
  interrupted = true;
  process.exitCode = signal === 'SIGINT' ? 130 : 143;
  await composeDown();
  releaseKeepAlive?.();
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    void handleSignal(signal);
  });
}

async function main() {
  try {
    preflightDocker();
  } catch (error) {
    console.error(REQUIREMENT_MESSAGE);
    console.error(`Detected problem: ${error.message}`);
    process.exitCode = 1;
    return;
  }

  try {
    startupAttempted = true;
    await run('docker', ['compose', 'up', '--build', '--wait']);
    await Promise.all([
      waitForUrl(API_READY_URL, 'PARTHA API'),
      waitForUrl(FRONTEND_URL, 'PARTHA frontend'),
    ]);

    console.log('PARTHA is ready at http://localhost:5173');
    await new Promise((resolve) => {
      const keepAliveTimer = setInterval(() => {}, 24 * 60 * 60 * 1000);
      releaseKeepAlive = () => {
        clearInterval(keepAliveTimer);
        resolve();
      };
    });
  } catch (error) {
    if (interrupted) {
      await composeDown();
      return;
    }
    console.error(`PARTHA failed to start: ${error.message}`);
    if (startupAttempted) showDiagnostics();
    process.exitCode = 1;
    await composeDown();
  }
}

await main();
