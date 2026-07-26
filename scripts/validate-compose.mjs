import { randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import http from "node:http";

const API_BASE_URL = "http://127.0.0.1:8000";
const POSTGRES_USER = process.env.POSTGRES_USER || "partha";
const POSTGRES_DB = process.env.POSTGRES_DB || "partha";

// A tiny, stable public repository (no supported source files) — already used
// as this API's own OpenAPI example, so it is known to import cleanly.
const FIXTURE_REPOSITORY_URL = "https://github.com/octocat/Hello-World";
const FIXTURE_REPOSITORY_BRANCH = "master";

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit", shell: false });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}`);
  }
}

function runCapture(command, args) {
  const result = spawnSync(command, args, { stdio: ["ignore", "pipe", "inherit"], shell: false, encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}`);
  }
  return result.stdout;
}

function dockerComposeExec(service, args) {
  run("docker", ["compose", "exec", "-T", service, ...args]);
}

function dockerComposeExecCapture(service, args) {
  return runCapture("docker", ["compose", "exec", "-T", service, ...args]);
}

function dockerComposeExecWithEnv(service, env, args) {
  const envFlags = Object.entries(env).flatMap(([key, value]) => ["-e", `${key}=${value}`]);
  run("docker", ["compose", "exec", "-T", ...envFlags, service, ...args]);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function assert(condition, message) {
  if (!condition) throw new Error(`Assertion failed: ${message}`);
}

function randomSuffix() {
  return randomBytes(4).toString("hex");
}

function checkReady() {
  return new Promise((resolve) => {
    const request = http.get(`${API_BASE_URL}/ready`, { timeout: 5000 }, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on("timeout", () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

async function waitUntilReady({ attempts = 30, intervalMs = 2000, label = "startup" } = {}) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await checkReady()) return;
    await sleep(intervalMs);
  }
  run("docker", ["compose", "logs", "api", "postgres", "redis"]);
  throw new Error(`Compose API did not become ready during ${label} (waited ${(attempts * intervalMs) / 1000}s).`);
}

async function apiFetch(path, { method = "GET", token, body, expectedStatuses = [200] } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let requestBody;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: requestBody });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!expectedStatuses.includes(response.status)) {
    throw new Error(`${method} ${path} expected status in [${expectedStatuses.join(", ")}], got ${response.status}: ${text}`);
  }
  return { status: response.status, payload };
}

// --- 1. Migrations ---------------------------------------------------------

async function verifyMigrations(knownSecrets) {
  console.log("[migrations] re-running alembic upgrade head against the live app database");
  dockerComposeExec("api", ["alembic", "upgrade", "head"]);

  console.log("[migrations] asserting core tables exist");
  const tableList = dockerComposeExecCapture("postgres", [
    "psql",
    "-U",
    POSTGRES_USER,
    "-d",
    POSTGRES_DB,
    "-tAc",
    "select tablename from pg_tables where schemaname='public'",
  ]);
  for (const table of ["repositories", "analysis_jobs", "ri_snapshots"]) {
    assert(tableList.includes(table), `expected core table "${table}" to exist after migration`);
  }

  console.log("[migrations] proving a downgrade/upgrade round trip is clean");
  dockerComposeExec("api", ["alembic", "downgrade", "-1"]);
  dockerComposeExec("api", ["alembic", "upgrade", "head"]);

  await verifyPercentEncodedDatabaseUrl(knownSecrets);
}

// Regression coverage for #110: Alembic's ConfigParser previously choked on a
// raw "%" in DATABASE_URL (e.g. a percent-encoded "@" in a password), because
// set_main_option() treats "%" as its own interpolation syntax unless escaped.
// This proves a real, live connection with such a password migrates cleanly,
// isolated in a scratch role/database so it never touches the app's own data.
async function verifyPercentEncodedDatabaseUrl(knownSecrets) {
  console.log("[migrations] verifying a percent-encoded DATABASE_URL password (#110 regression)");
  const scratchUser = "migration_check_user";
  const scratchDb = "migration_check_db";
  const scratchPassword = `p@rtha-${randomSuffix()}`;
  knownSecrets.push(scratchPassword);
  const encodedPassword = encodeURIComponent(scratchPassword);
  const scratchUrl = `postgresql+psycopg://${scratchUser}:${encodedPassword}@postgres:5432/${scratchDb}`;

  const createScratch = () =>
    run("docker", [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      POSTGRES_USER,
      "-d",
      POSTGRES_DB,
      "-v",
      "ON_ERROR_STOP=1",
      "-c",
      `DROP DATABASE IF EXISTS ${scratchDb};`,
      "-c",
      `DROP ROLE IF EXISTS ${scratchUser};`,
      "-c",
      `CREATE ROLE ${scratchUser} LOGIN PASSWORD '${scratchPassword}';`,
      "-c",
      `CREATE DATABASE ${scratchDb} OWNER ${scratchUser};`,
    ]);
  const dropScratch = () =>
    run("docker", [
      "compose",
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      POSTGRES_USER,
      "-d",
      POSTGRES_DB,
      "-v",
      "ON_ERROR_STOP=1",
      "-c",
      `DROP DATABASE IF EXISTS ${scratchDb};`,
      "-c",
      `DROP ROLE IF EXISTS ${scratchUser};`,
    ]);

  createScratch();
  try {
    dockerComposeExecWithEnv("api", { DATABASE_URL: scratchUrl }, ["alembic", "upgrade", "head"]);
    dockerComposeExecWithEnv("api", { DATABASE_URL: scratchUrl }, ["alembic", "downgrade", "-1"]);
    dockerComposeExecWithEnv("api", { DATABASE_URL: scratchUrl }, ["alembic", "upgrade", "head"]);
  } finally {
    dropScratch();
  }
}

// --- 2. Auth + owner isolation ---------------------------------------------

async function registerUser(email, password) {
  const { payload } = await apiFetch("/auth/register", {
    method: "POST",
    body: { email, password },
    expectedStatuses: [201],
  });
  return payload;
}

async function createFixtureRepository(token) {
  const { payload } = await apiFetch("/repositories/github", {
    method: "POST",
    token,
    body: { url: FIXTURE_REPOSITORY_URL, branch: FIXTURE_REPOSITORY_BRANCH },
    expectedStatuses: [201],
  });
  return payload;
}

async function verifyAuthAndOwnerIsolation(knownSecrets) {
  console.log("[auth] registering two disposable users");
  const suffix = randomSuffix();
  const user1Email = `acceptance-user1-${suffix}@example.com`;
  const user2Email = `acceptance-user2-${suffix}@example.com`;
  const user1Password = `Accept-${suffix}-user1!`;
  const user2Password = `Accept-${suffix}-user2!`;
  knownSecrets.push(user1Password, user2Password);

  const user1 = await registerUser(user1Email, user1Password);
  const user2 = await registerUser(user2Email, user2Password);
  assert(user1.accessToken, "user1 registration did not return an access token");
  assert(user2.accessToken, "user2 registration did not return an access token");

  console.log("[auth] user1 creating a fixture repository");
  const repository = await createFixtureRepository(user1.accessToken);
  assert(repository.id, "repository creation did not return an id");

  console.log("[auth] asserting owner isolation: user2 must get 404 on user1's repository");
  const isolationCheck = await apiFetch(`/repositories/${repository.id}`, {
    token: user2.accessToken,
    expectedStatuses: [404],
  });
  assert(isolationCheck.status === 404, "owner isolation violated: user2 could read user1's repository");

  return { user1, user2, repository };
}

// --- 3. Analysis lifecycle --------------------------------------------------

// Mirrors the frontend's resilient polling (fix/164, 1ca0daf): tolerate
// transient connection failures with capped exponential backoff, stop the
// instant a terminal status is observed, and give up cleanly at a deadline.
async function pollAnalysisUntilComplete(token, repositoryId, { timeoutMs = 120_000, intervalMs = 2000, maxNetworkRetries = 5 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let networkRetries = 0;
  while (Date.now() < deadline) {
    let response;
    try {
      response = await apiFetch(`/analysis/${repositoryId}/status`, { token, expectedStatuses: [200] });
    } catch (error) {
      networkRetries += 1;
      if (networkRetries > maxNetworkRetries) {
        throw new Error(`Analysis status polling lost connectivity after ${maxNetworkRetries} retries: ${error.message}`);
      }
      await sleep(Math.min(15_000, 1000 * 2 ** (networkRetries - 1)));
      continue;
    }
    networkRetries = 0;
    const { status } = response.payload;
    if (status === "completed") return response.payload;
    if (status === "failed" || status === "cancelled") {
      throw new Error(`Analysis ended in terminal state "${status}": ${response.payload.error ?? "no error detail"}`);
    }
    await sleep(intervalMs);
  }
  throw new Error(`Analysis did not reach a completed status within ${timeoutMs}ms`);
}

async function verifyAnalysisLifecycle(user1, repository) {
  console.log("[analysis] starting analysis and polling for completion");
  await apiFetch(`/analysis/${repository.id}/start`, { method: "POST", token: user1.accessToken, expectedStatuses: [200] });
  const finalStatus = await pollAnalysisUntilComplete(user1.accessToken, repository.id);
  assert(finalStatus.status === "completed", "analysis did not reach completed status");

  console.log("[analysis] asserting a sealed ri.v1 snapshot exists for this revision");
  const manifest = await apiFetch(`/analysis/${repository.id}/revision-manifest`, {
    token: user1.accessToken,
    expectedStatuses: [200],
  });
  const { manifest: body } = manifest.payload;
  assert(
    body.snapshotSchemaVersion === "ri.v1",
    `expected a sealed ri.v1 snapshot, got schema version "${body.snapshotSchemaVersion}"`,
  );
  assert(body.canonicalGraphHash, "sealed snapshot is missing its canonical graph hash");
  assert(body.sealedAt, "sealed snapshot is missing its sealedAt timestamp");
  assert(
    manifest.payload.verificationState === "verified",
    `expected verification state "verified", got "${manifest.payload.verificationState}"`,
  );

  return { snapshotId: body.snapshotId, canonicalGraphHash: body.canonicalGraphHash };
}

// --- 4. Restart / recovery ---------------------------------------------------

async function verifyRestartRecovery(user1, repository, snapshot) {
  console.log("[restart] restarting the api container");
  run("docker", ["compose", "restart", "api"]);
  await waitUntilReady({ label: "post-restart" });

  console.log("[restart] asserting the repository and completed analysis survived the restart");
  const repoCheck = await apiFetch(`/repositories/${repository.id}`, { token: user1.accessToken, expectedStatuses: [200] });
  assert(repoCheck.payload.id === repository.id, "repository missing or changed identity after restart");

  const statusCheck = await apiFetch(`/analysis/${repository.id}/status`, { token: user1.accessToken, expectedStatuses: [200] });
  assert(statusCheck.payload.status === "completed", "analysis job lost its completed status after restart");

  const manifestCheck = await apiFetch(`/analysis/${repository.id}/revision-manifest`, {
    token: user1.accessToken,
    expectedStatuses: [200],
  });
  assert(
    manifestCheck.payload.manifest.canonicalGraphHash === snapshot.canonicalGraphHash,
    "sealed snapshot's canonical graph hash changed across restart (possible data corruption)",
  );

  console.log("[restart] asserting no orphaned or in-flight job rows at the database level");
  const jobStatuses = dockerComposeExecCapture("postgres", [
    "psql",
    "-U",
    POSTGRES_USER,
    "-d",
    POSTGRES_DB,
    "-tAc",
    `select status from analysis_jobs where repository_id='${repository.id}'`,
  ])
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  assert(jobStatuses.length === 1, `expected exactly one analysis job row for the repository, found ${jobStatuses.length}`);
  assert(jobStatuses[0] === "completed", `orphaned or in-flight job detected after restart: status="${jobStatuses[0]}"`);
}

// --- 5. Backup / restore ------------------------------------------------------

async function verifyBackupRestore(snapshot) {
  console.log("[backup] proving a pg_dump/pg_restore round trip preserves the sealed snapshot");
  const restoreDb = "partha_restore_check";
  run("docker", [
    "compose",
    "exec",
    "-T",
    "postgres",
    "sh",
    "-c",
    `dropdb -U ${POSTGRES_USER} --if-exists ${restoreDb} && ` +
      `createdb -U ${POSTGRES_USER} -O ${POSTGRES_USER} ${restoreDb} && ` +
      `pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | psql -U ${POSTGRES_USER} -d ${restoreDb}`,
  ]);
  try {
    const restoredHash = dockerComposeExecCapture("postgres", [
      "psql",
      "-U",
      POSTGRES_USER,
      "-d",
      restoreDb,
      "-tAc",
      `select canonical_graph_hash from ri_snapshots where snapshot_id='${snapshot.snapshotId}'`,
    ]).trim();
    assert(
      restoredHash === snapshot.canonicalGraphHash,
      `backup/restore round trip produced a different canonical_graph_hash (expected ${snapshot.canonicalGraphHash}, got ${restoredHash})`,
    );
  } finally {
    run("docker", ["compose", "exec", "-T", "postgres", "dropdb", "-U", POSTGRES_USER, "--if-exists", restoreDb]);
  }
}

// --- 6. Secrets in logs -------------------------------------------------------

function assertNoSecretsInLogs(knownSecrets) {
  console.log("[secrets] checking docker compose logs for verbatim secret values");
  const logs = runCapture("docker", ["compose", "logs", "--no-color"]);
  for (const secret of knownSecrets) {
    if (secret && logs.includes(secret)) {
      throw new Error("A known secret value from this run was found verbatim in `docker compose logs` output.");
    }
  }
}

// --- main --------------------------------------------------------------------

async function main() {
  run("docker", ["compose", "config"]);
  const knownSecrets = [];
  let failure = null;
  try {
    run("docker", ["compose", "up", "--build", "-d"]);
    await waitUntilReady({ label: "initial startup" });

    await verifyMigrations(knownSecrets);
    const { user1, repository } = await verifyAuthAndOwnerIsolation(knownSecrets);
    const snapshot = await verifyAnalysisLifecycle(user1, repository);
    await verifyRestartRecovery(user1, repository, snapshot);
    await verifyBackupRestore(snapshot);

    console.log(
      "Acceptance sequence passed: migrations, auth/owner isolation, analysis lifecycle, restart/recovery, and backup/restore all verified.",
    );
  } catch (error) {
    failure = error;
  } finally {
    try {
      assertNoSecretsInLogs(knownSecrets);
    } catch (secretsError) {
      failure = failure ?? secretsError;
      console.error(secretsError.message);
    }
    run("docker", ["compose", "down", "-v"]);
  }
  if (failure) throw failure;
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
