#!/usr/bin/env node
/**
 * Policy-aware frontend dependency audit gate (#154).
 *
 * `npm audit` alone is a poor gate: it exits non-zero on advisories whose fix
 * is a major migration, and it treats a build-tool transitive the same as
 * something shipped to a browser. This wraps it with two ideas:
 *
 *  1. Runtime exposure is separated from development-only exposure, by running
 *     the audit a second time with `--omit=dev`. Anything present in the full
 *     audit but absent from the runtime audit reaches only developer machines
 *     and CI, never a user's browser.
 *
 *  2. An advisory may be acknowledged, but the acknowledgement stays valid only
 *     while what it described is still true. It fails the build when it
 *     expires, when the advisory stops naming the accepted package, when the
 *     lockfile moves the accepted package to a different version, when our own
 *     source starts touching the affected surface, or when the advisory
 *     disappears entirely and the exception is left behind.
 *
 * npm's "No fix available" means npm cannot apply a fix automatically -- often
 * because the fix is a major version bump. It does NOT mean no patched release
 * exists. Record the real patched version in the policy.
 *
 * Note on invocation: the repository root declares npm workspaces but has no
 * lockfile, so `npm audit` from the root or from apps/frontend fails with
 * ENOLOCK. `--prefix apps/frontend` resolves against the frontend lockfile,
 * which is the same file CI installs from via `npm ci --prefix apps/frontend`.
 */

import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const policyPath = join(repoRoot, 'scripts', 'dependency-audit-policy.json');

/** Severities that fail the build when they reach a user's browser. */
const RUNTIME_FAIL_AT = new Set(['moderate', 'high', 'critical']);
/** Development-only exposure tolerates moderate findings but not these. */
const DEV_FAIL_AT = new Set(['high', 'critical']);

function audit(extraArgs) {
  const args = ['audit', '--json', '--prefix', 'apps/frontend', ...extraArgs];
  let stdout;
  try {
    stdout = execFileSync('npm', args, { cwd: repoRoot, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  } catch (error) {
    // npm audit exits non-zero when it finds anything; the report is still on
    // stdout. A genuinely broken invocation produces no parseable JSON.
    stdout = error.stdout;
    if (!stdout) {
      console.error(`npm ${args.join(' ')} failed:\n${error.stderr || error.message}`);
      process.exit(2);
    }
  }
  return JSON.parse(stdout);
}

/** Map advisory id -> { id, title, severity, url, packages:Set } */
function advisories(report) {
  const found = new Map();
  for (const [name, vulnerability] of Object.entries(report.vulnerabilities || {})) {
    for (const via of vulnerability.via || []) {
      // A string `via` is an indirection to another vulnerable package; the
      // advisory object itself is recorded on that package's own entry.
      if (typeof via !== 'object' || via.source === undefined) continue;
      const id = via.url?.split('/').pop() || String(via.source);
      const existing = found.get(id);
      if (existing) {
        existing.packages.add(name);
        continue;
      }
      found.set(id, {
        id,
        title: via.title || '(untitled advisory)',
        severity: via.severity || 'unknown',
        url: via.url || '',
        packages: new Set([name]),
      });
    }
  }
  return found;
}

/** Version of a package as pinned by the frontend lockfile, or null. */
function lockedVersion(name) {
  const lock = JSON.parse(readFileSync(join(repoRoot, 'apps', 'frontend', 'package-lock.json'), 'utf8'));
  return lock.packages?.[`node_modules/${name}`]?.version ?? null;
}

/**
 * Source files under a policy root, so a reachability guard can be evaluated
 * against our own code rather than against the dependency tree.
 */
function sourceFiles(root) {
  const found = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx|js|jsx|mjs|cjs)$/.test(entry.name)) found.push(full);
    }
  };
  try {
    walk(join(repoRoot, root));
  } catch {
    return [];
  }
  return found;
}

/**
 * An acknowledgement is only valid while the thing it described is still the
 * thing in front of us. Anything else means a human needs to look again.
 */
function validateAcknowledgement(entry, advisory, today) {
  const problems = [];

  if (entry.reviewBy < today) {
    problems.push(`acknowledgement expired on ${entry.reviewBy}; re-review it`);
  }

  // Identity: the advisory must still concern the package we accepted it for.
  if (entry.package && !advisory.packages.has(entry.package)) {
    problems.push(
      `acknowledgement names package "${entry.package}" but the advisory now affects ` +
        `${[...advisory.packages].join(', ')}; re-review it`,
    );
  }

  // Version drift: accepting a risk for one version is not accepting it for
  // whatever the lockfile drifts to next.
  if (entry.acceptedVersion) {
    const installed = lockedVersion(entry.package);
    if (installed === null) {
      problems.push(`"${entry.package}" is no longer in the lockfile; remove the acknowledgement`);
    } else if (installed !== entry.acceptedVersion) {
      problems.push(
        `accepted for ${entry.package}@${entry.acceptedVersion} but the lockfile now pins ` +
          `${installed}; re-review it`,
      );
    }
  }

  // Reachability: the acceptance rests on us not using the affected surface.
  // If that stops being true, the acceptance stops being valid.
  const reachability = entry.reachability;
  if (reachability?.forbiddenPatterns?.length) {
    const hits = [];
    for (const root of reachability.roots || []) {
      for (const file of sourceFiles(root)) {
        const text = readFileSync(file, 'utf8');
        for (const pattern of reachability.forbiddenPatterns) {
          if (text.includes(pattern)) {
            hits.push(`${file.replace(`${repoRoot}/`, '')} uses "${pattern}"`);
          }
        }
      }
    }
    if (hits.length) {
      problems.push(
        `the accepted advisory may now be reachable; the acceptance assumed otherwise:\n      ` +
          hits.slice(0, 10).join('\n      '),
      );
    }
  }

  return problems;
}

export { advisories, validateAcknowledgement };

// Importing this module (from its tests) must not run the audit.
if (process.argv[1] !== fileURLToPath(import.meta.url)) {
  // eslint-disable-next-line no-empty-function
} else {

const policy = JSON.parse(readFileSync(policyPath, 'utf8'));
const acknowledged = new Map((policy.acknowledged || []).map((entry) => [entry.id, entry]));

const full = advisories(audit([]));
const runtime = advisories(audit(['--omit=dev']));

const today = new Date().toISOString().slice(0, 10);
const failures = [];
const accepted = [];

for (const [id, advisory] of full) {
  const isRuntime = runtime.has(id);
  const scope = isRuntime ? 'runtime' : 'development-only';
  const failAt = isRuntime ? RUNTIME_FAIL_AT : DEV_FAIL_AT;
  const acknowledgement = acknowledged.get(id);
  const label = `${advisory.severity.padEnd(8)} ${scope.padEnd(16)} ${id} ${advisory.title}`;

  if (acknowledgement) {
    const problems = validateAcknowledgement(acknowledgement, advisory, today);
    if (problems.length) {
      failures.push(`${label}\n    ${problems.join('\n    ')}`);
    } else {
      accepted.push(`${label}\n    accepted until ${acknowledgement.reviewBy}: ${acknowledgement.reason}`);
    }
    continue;
  }

  if (failAt.has(advisory.severity)) {
    failures.push(`${label}\n    packages: ${[...advisory.packages].join(', ')}\n    ${advisory.url}`);
  } else {
    accepted.push(`${label} (below the ${scope} threshold)`);
  }
}

// An acknowledgement for an advisory that no longer appears is stale: the
// dependency was fixed or removed, and the exception should go with it.
for (const [id, entry] of acknowledged) {
  if (!full.has(id)) {
    failures.push(`stale acknowledgement ${id} no longer matches any advisory; remove it\n    reason was: ${entry.reason}`);
  }
}

console.log('Frontend dependency audit');
console.log('=========================');
if (accepted.length) {
  console.log('\nAccepted:');
  for (const line of accepted) console.log(`  ${line}`);
}
if (failures.length) {
  console.log('\nBlocking:');
  for (const line of failures) console.log(`  ${line}`);
  console.log(`\n${failures.length} blocking finding(s).`);
  console.log('Fix the advisory, or add a reviewed acknowledgement to scripts/dependency-audit-policy.json.');
  process.exit(1);
}
console.log(`\nNo blocking findings (${accepted.length} accepted).`);
}
