import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  expect,
  test,
  type Page,
} from '@playwright/test';
import type {
  AxeResults,
  NodeResult,
  RunOptions,
  Result,
} from 'axe-core';

interface Fixture {
  label: string;
  id: string;
  name: string;
}

interface Fixtures {
  email: string;
  password: string;
  repos: Fixture[];
}

const FIXTURES: Fixtures = JSON.parse(
  readFileSync(process.env.PARTHA_VISUAL_FIXTURES ?? '/tmp/partha-prototype-fixtures.json', 'utf8'),
);
const AXE_SOURCE_PATH = fileURLToPath(
  new URL('../node_modules/axe-core/axe.min.js', import.meta.url),
);
const WCAG_22_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'];

interface KnownFinding {
  issue: number;
  rule: string;
  testId: string;
  count: number;
}

const SHELL_FINDINGS: KnownFinding[] = [
  { issue: 236, rule: 'button-name', testId: 'notification-menu-trigger', count: 1 },
  { issue: 236, rule: 'button-name', testId: 'user-menu-trigger', count: 1 },
  { issue: 238, rule: 'color-contrast', testId: 'secondary-navigation-label', count: 1 },
];

function byLabel(label: string) {
  const fixture = FIXTURES.repos.find((repository) => repository.label === label);
  if (!fixture) throw new Error(`fixture "${label}" missing`);
  return fixture;
}

function nodeHasTestId(node: NodeResult, testId: string) {
  return node.html.includes(`data-testid="${testId}"`);
}

function describeViolations(state: string, violations: Result[]) {
  if (violations.length === 0) return `${state}: no axe violations`;
  return [
    `${state}: ${violations.length} axe violation(s)`,
    ...violations.flatMap((violation) => [
      `${violation.id} (${violation.impact ?? 'unknown'}): ${violation.help}`,
      `  ${violation.helpUrl}`,
      ...violation.nodes.map((node) => [
        `  target: ${node.target.join(' > ')}`,
        `  html: ${node.html}`,
        `  ${node.failureSummary ?? 'No failure summary supplied.'}`,
      ].join('\n')),
    ]),
  ].join('\n');
}

async function expectWcagBaseline(
  page: Page,
  state: string,
  knownFindings: KnownFinding[] = [],
) {
  await page.waitForFunction(() => document.getAnimations().every((animation) => {
    const iterations = animation.effect?.getComputedTiming().iterations;
    return iterations === Infinity
      || animation.playState === 'finished'
      || animation.playState === 'idle';
  }));
  await page.addScriptTag({ path: AXE_SOURCE_PATH });
  const violations = await page.evaluate(
    async ({ tags }) => {
      const axe = (window as typeof window & {
        axe: {
          run(
            context?: Document,
            options?: RunOptions,
          ): Promise<AxeResults>;
        };
      }).axe;
      const results = await axe.run(document, {
        runOnly: { type: 'tag', values: tags },
        resultTypes: ['violations'],
      });
      return results.violations;
    },
    { tags: WCAG_22_AA_TAGS },
  );

  const actualNodes = violations.flatMap((violation) => violation.nodes.map((node) => ({
    rule: violation.id,
    node,
  })));
  for (const finding of knownFindings) {
    const matches = actualNodes.filter(
      ({ rule, node }) => rule === finding.rule && nodeHasTestId(node, finding.testId),
    );
    expect(
      matches,
      `${state}: expected the exact known baseline for #${finding.issue} `
        + `(${finding.rule}, ${finding.testId})`,
    ).toHaveLength(finding.count);
  }

  const unexpected = violations
    .map((violation) => ({
      ...violation,
      nodes: violation.nodes.filter((node) => !knownFindings.some(
        (finding) => finding.rule === violation.id && nodeHasTestId(node, finding.testId),
      )),
    }))
    .filter((violation) => violation.nodes.length > 0);

  expect(unexpected, describeViolations(state, unexpected)).toHaveLength(0);
}

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(FIXTURES.email);
  await page.getByLabel(/password/i).fill(FIXTURES.password);
  await page.getByRole('button', { name: /sign in|log ?in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 });
}

async function openSurface(page: Page, name: string) {
  await page
    .getByRole('navigation', { name: 'Primary navigation' })
    .getByRole('link', { name, exact: true })
    .click();
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible({ timeout: 15_000 });
}

async function selectRepository(page: Page, fixture: Fixture) {
  const trigger = page.locator('header button').filter({
    hasText: /^(No repository|small|medium|large-multi|large-single|long-labels|disconnected-unresolved|unanalysed)$/,
  }).first();
  await trigger.click();
  await page.locator('button').filter({ hasText: new RegExp(`^${fixture.name}$`) }).last().click();
  await expect(trigger).toHaveText(fixture.name);
}

test.describe('WCAG 2.2 AA automated baseline (#118)', () => {
  test('login form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Sign in to PARTHA' })).toBeVisible();

    await expectWcagBaseline(page, 'login: initial sign-in form', [
      { issue: 240, rule: 'link-in-text-block', testId: 'login-register-link', count: 1 },
    ]);
  });

  test('authenticated application shell and sidebar', async ({ page }) => {
    await login(page);
    await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();

    await expectWcagBaseline(
      page,
      'application shell/sidebar: authenticated dashboard',
      SHELL_FINDINGS,
    );
  });

  test('repository list', async ({ page }) => {
    await login(page);
    await openSurface(page, 'Repositories');
    await expect(page.getByRole('button', { name: byLabel('small').name, exact: true })).toBeVisible();
    await expectWcagBaseline(page, 'repositories: seeded success list', [
      ...SHELL_FINDINGS,
      {
        issue: 235,
        rule: 'button-name',
        testId: 'repository-open-action',
        count: FIXTURES.repos.length,
      },
      {
        issue: 235,
        rule: 'button-name',
        testId: 'repository-delete-action',
        count: FIXTURES.repos.length,
      },
    ]);
  });

  test('GitHub repository import form', async ({ page }) => {
    await login(page);
    await openSurface(page, 'Repositories');
    await page.getByRole('button', { name: 'Upload New' }).click();
    await expect(page.getByRole('heading', { name: 'Upload Repository' })).toBeVisible();
    await page.getByRole('button', { name: 'GitHub URL', exact: true }).click();
    await expect(page.getByText('Import from GitHub')).toBeVisible();
    await expectWcagBaseline(page, 'repository import: empty GitHub URL form', [
      ...SHELL_FINDINGS,
      { issue: 237, rule: 'color-contrast', testId: 'github-import-helper', count: 1 },
      { issue: 237, rule: 'color-contrast', testId: 'github-import-label', count: 1 },
    ]);
  });

  test('architecture graph', async ({ page }) => {
    await login(page);
    await openSurface(page, 'Architecture');
    await selectRepository(page, byLabel('small'));
    await expect(page.locator('.react-flow__node').first()).toBeVisible({ timeout: 20_000 });

    await expectWcagBaseline(page, 'architecture: seeded small graph', SHELL_FINDINGS);
  });

  test('architecture node inspector', async ({ page }) => {
    await login(page);
    await openSurface(page, 'Architecture');
    await selectRepository(page, byLabel('small'));
    const node = page.locator('.react-flow__node').first();
    await expect(node).toBeVisible({ timeout: 20_000 });
    await node.click();
    await expect(page.getByRole('dialog', { name: /architecture node/i })).toBeVisible();

    await expectWcagBaseline(page, 'node inspector: first node selected', SHELL_FINDINGS);
  });
});
