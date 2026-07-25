/**
 * Tests for the dependency-audit policy gate (#154).
 *
 * The gate's value is entirely in when it *refuses* to stay quiet. These cover
 * each condition under which an acknowledgement must stop being accepted.
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

/** The real react-router entry, so the tests bind to the shipped policy. */
const reactRouterEntry = policy.acknowledged.find((entry) => entry.id === 'GHSA-qwww-vcr4-c8h2');

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

test('the shipped react-router acknowledgement is currently valid', () => {
  assert.ok(reactRouterEntry, 'expected a GHSA-qwww-vcr4-c8h2 acknowledgement');
  const problems = validateAcknowledgement(reactRouterEntry, advisoryFor(reactRouterEntry), TODAY);
  assert.deepEqual(problems, []);
});

test('the react-router acknowledgement records the real patched version', () => {
  // The earlier version of this policy claimed no patched release existed.
  // GitHub lists 8.3.0 as patched, so the policy must say so and must not
  // repeat npm's "No fix available" as if it meant the same thing.
  assert.equal(reactRouterEntry.patchedVersion, '8.3.0');
  assert.match(reactRouterEntry.reason, /8\.3\.0 as patched/);
  assert.doesNotMatch(reactRouterEntry.reason, /no fixed release exists/i);
  assert.match(reactRouterEntry.reason, /does not claim that no patched version exists/i);
});

test('an expired acknowledgement fails', () => {
  const entry = { ...reactRouterEntry, reviewBy: '2020-01-01' };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /expired on 2020-01-01/);
});

test('an acknowledgement fails when the advisory no longer names the accepted package', () => {
  const entry = { ...reactRouterEntry, reviewBy: FUTURE };
  const advisory = advisoryFor(entry, { packages: new Set(['some-other-package']) });
  const problems = validateAcknowledgement(entry, advisory, TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /but the advisory now affects some-other-package/);
});

test('an acknowledgement fails when the accepted package version changes', () => {
  const entry = { ...reactRouterEntry, reviewBy: FUTURE, acceptedVersion: '7.0.0' };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /accepted for react-router@7\.0\.0 but the lockfile now pins/);
});

test('an acknowledgement fails when the accepted package leaves the lockfile', () => {
  const entry = {
    ...reactRouterEntry,
    reviewBy: FUTURE,
    package: 'package-that-is-not-installed',
    acceptedVersion: '1.0.0',
  };
  const problems = validateAcknowledgement(entry, advisoryFor(entry), TODAY);
  assert.ok(problems.some((problem) => /no longer in the lockfile/.test(problem)));
});

test('an acknowledgement fails when the affected surface becomes reachable', () => {
  // The react-router acceptance rests on PARTHA never touching unstable RSC or
  // server APIs. Point the guard at a root that does contain one of its own
  // forbidden patterns to prove the check actually fires.
  const entry = {
    ...reactRouterEntry,
    reviewBy: FUTURE,
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

test('the real reachability guard finds nothing in the frontend source today', () => {
  const problems = validateAcknowledgement(
    { ...reactRouterEntry, reviewBy: FUTURE },
    advisoryFor(reactRouterEntry),
    TODAY,
  );
  assert.deepEqual(problems, [], 'frontend source must not use unstable or server React Router APIs');
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
