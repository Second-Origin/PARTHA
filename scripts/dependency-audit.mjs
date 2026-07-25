#!/usr/bin/env node
/**
 * Policy-aware frontend dependency audit gate (#154).
 *
 * `npm audit` alone is a poor gate: it fails on advisories that cannot be
 * fixed, and it treats a build-tool transitive the same as something shipped
 * to a browser. This wraps it with two ideas:
 *
 *  1. Runtime exposure is separated from development-only exposure, by running
 *     the audit a second time with `--omit=dev`. Anything present in the full
 *     audit but absent from the runtime audit reaches only developer machines
 *     and CI, never a user's browser.
 *
 *  2. An advisory may be acknowledged, but only with a written reason and a
 *     review date. An expired acknowledgement fails the build, so "we looked at
 *     this once" cannot silently become "we stopped looking".
 *
 * Note on invocation: the repository root declares npm workspaces but has no
 * lockfile, so `npm audit` from the root or from apps/frontend fails with
 * ENOLOCK. `--prefix apps/frontend` resolves against the frontend lockfile,
 * which is the same file CI installs from via `npm ci --prefix apps/frontend`.
 */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
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
    if (acknowledgement.reviewBy < today) {
      failures.push(`${label}\n    acknowledgement expired on ${acknowledgement.reviewBy}; re-review it`);
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
