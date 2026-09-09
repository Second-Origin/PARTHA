/**
 * Tests for the dependency-audit policy gate (#154).
 *
 * The gate's value is entirely in when it *refuses* to stay quiet. These cover
 * each condition under which an acknowledgement must stop being accepted.
 *
 * The behavioural tests deliberately use *synthetic* entries rather than
 * binding to whichever exception happens to be shipped today. An earlier
 * version of this file used the live react-router entry as its fixture, so
 * retiring that exception — the correct action once the advisory was patched
 * in 7.18.2 — broke five tests at once. A gate that fails when you fix the
 * vulnerability it guards is worse than no gate: it teaches you to keep the
 * exception. Structural expectations about the shipped policy live in their
 * own tests below and hold for any entry, including none.
 *
 * Run with: node --test scripts/
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { advisories, validateAcknowledgement } from './dependency-audit.mjs';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const policy = JSON.parse(readFileSync(join(repoRoot, 'scripts', 'dependency-audit-policy.json'), 'utf8'));

const FUTURE = '2099-01-01';
const TODAY = '2026-07-25';

/**
 * A synthetic acknowledgement. `react-router` is a real lockfile entry, so the
 * version-drift checks exercise the real lookup, but no assertion depends on
 * which version is pinned today.
 */
const syntheticEntry = {
  id: 'GHSA-test-0000-0000',
  package: 'react-router',
  severity: 'high',
  reason: 'synthetic fixture for the policy-gate tests',
  reviewBy: FUTURE,
};

function advisoryFor(entry, overrides = {}) {
  return {
    id: entry.id,
    title: 'test advisory',
    severity: entry.severity,
    url: `https://github.com/advisories/${entry.id}`,
    packages: new Set([entry.package]),
    ...overrides,
  };
}

test('a current acknowledgement with no drift is accepted', () => {
  const problems = validateAcknowledgement(syntheticEntry, advisoryFor(syntheticEntry), TODAY);
  assert.deepEqual(problems, []);
});

test('an expired acknowledgement fails', () => {
  const entry = { ...syntheticEntry, reviewBy: '2020-01-01' };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /expired on 2020-01-01/);
});

test('an acknowledgement fails when the advisory no longer names the accepted package', () => {
  const advisory = advisoryFor(syntheticEntry, { packages: new Set(['some-other-package']) });
  const problems = validateAcknowledgement(syntheticEntry, advisory, TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /but the advisory now affects some-other-package/);
});

test('an acknowledgement fails when the accepted package version changes', () => {
  // A version the lockfile will never pin, so this stays true across bumps.
  const entry = { ...syntheticEntry, acceptedVersion: '0.0.0-not-a-real-release' };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /accepted for react-router@0\.0\.0-not-a-real-release but the lockfile now pins/);
});

test('an acknowledgement fails when the accepted package leaves the lockfile', () => {
  const entry = {
    ...syntheticEntry,
    package: 'package-that-is-not-installed',
    acceptedVersion: '1.0.0',
  };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.ok(problems.some((problem) => /no longer in the lockfile/.test(problem)));
});

test('an acknowledgement fails when the affected surface becomes reachable', () => {
  // Point the guard at a root that does contain one of its own forbidden
  // patterns to prove the check actually fires.
  const entry = {
    ...syntheticEntry,
    reachability: {
      roots: ['scripts'],
      forbiddenPatterns: ['createStaticHandler'],
    },
  };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /may now be reachable/);
  assert.match(problems[0], /createStaticHandler/);
});

test('the frontend source uses no unstable or server-side React Router surface', () => {
  // Kept independent of any shipped acknowledgement: PARTHA is a client-only
  // Vite SPA, and the RSC/server React Router surface is where this class of
  // advisory lives. This asserts that property directly, so it keeps holding
  // after an exception is retired.
  const entry = {
    ...syntheticEntry,
    reachability: {
      roots: ['apps/frontend/src'],
      forbiddenPatterns: [
        'unstable_',
        'createStaticHandler',
        'createStaticRouter',
        'StaticRouterProvider',
        'deserializeErrors',
        'react-router/server',
        '@react-router/node',
        '@react-router/express',
        '@react-router/serve',
      ],
    },
  };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.deepEqual(problems, [], 'frontend source must not use unstable or server React Router APIs');
});

test('every shipped acknowledgement is well-formed and still valid today', () => {
  // Holds for an empty policy, which is the healthy steady state: an
  // acknowledgement should exist only while a real advisory is unpatched.
  const today = new Date().toISOString().slice(0, 10);
  for (const entry of policy.acknowledged || []) {
    assert.ok(entry.id, 'each acknowledgement needs an advisory id');
    assert.ok(entry.package, `${entry.id} needs a package`);
    assert.ok(entry.reason, `${entry.id} needs a reviewable reason`);
    assert.ok(entry.reviewBy, `${entry.id} needs a reviewBy date`);
    assert.doesNotMatch(
      entry.reason,
      /no fixed release exists/i,
      `${entry.id} must not repeat npm's "No fix available" as if it meant no patch exists`,
    );
    assert.deepEqual(
      validateAcknowledgement(entry, advisoryFor(entry), today),
      [],
      `${entry.id} is no longer valid; re-review or remove it`,
    );
  }
});

test('advisories() groups npm audit output by advisory id', () => {
  const report = {
    vulnerabilities: {
      'pkg-a': {
        via: [
          { source: 1, url: 'https://github.com/advisories/GHSA-test-0000-0000', title: 't', severity: 'high' },
        ],
      },
      // A string `via` is an indirection and must not create an advisory.
      'pkg-b': { via: ['pkg-a'] },
    },
  };
  const found = advisories(report);
  assert.deepEqual([...found.keys()], ['GHSA-test-0000-0000']);
  assert.deepEqual([...found.get('GHSA-test-0000-0000').packages], ['pkg-a']);
});
