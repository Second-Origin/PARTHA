import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';

interface Fixture {
  label: string;
  id: string;
  name: string;
  revisionValue: string | null;
  snapshotId: string | null;
  reviewFindings: number;
}

interface Fixtures {
  apiUrl: string;
  email: string;
  password: string;
  repos: Fixture[];
}

const FIXTURES: Fixtures = JSON.parse(
  readFileSync(process.env.PARTHA_VISUAL_FIXTURES ?? '/tmp/partha-prototype-fixtures.json', 'utf8'),
);

function byLabel(label: string) {
  const fixture = FIXTURES.repos.find((repository) => repository.label === label);
  if (!fixture) throw new Error(`fixture "${label}" missing`);
  return fixture;
}

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(FIXTURES.email);
  await page.getByLabel(/password/i).fill(FIXTURES.password);
  await page.getByRole('button', { name: /sign in|log ?in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 });
}

async function openSurface(page: Page, name: string) {
  if ((page.viewportSize()?.width ?? 1440) < 768) {
    await page.getByRole('button', { name: 'Open navigation drawer' }).click();
  }
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

async function capture(target: Page | Locator, name: string, testInfo: TestInfo) {
  const body = await target.screenshot();
  await testInfo.attach(name, { body, contentType: 'image/png' });
  const directory = process.env.PARTHA_VISUAL_SCREENSHOT_DIR;
  if (directory) {
    mkdirSync(directory, { recursive: true });
    writeFileSync(join(directory, `${name}.png`), body);
  }
}

test.describe('snapshot-backed Review and Insights journeys', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('Review shows supported findings, exact evidence navigation, and no score', async ({
    page,
  }, testInfo) => {
    const fixture = byLabel('disconnected-unresolved');
    expect(fixture.reviewFindings).toBeGreaterThan(0);
    await openSurface(page, 'Engineering Review');
    await selectRepository(page, fixture);

    await expect(page.getByText(fixture.snapshotId!, { exact: true })).toBeVisible();
    await expect(page.getByText(/No overall score, grade, health percentage/i)).toBeVisible();
    await expect(page.getByText(/matching supported findings/i)).toContainText(
      String(fixture.reviewFindings),
    );
    await expect(page.getByText(/Not assessed/i).first()).toBeVisible();
    expect((await page.locator('body').innerText()).toLowerCase()).not.toMatch(
      /\boverall score:\s*\d|\bhealth score\b|\bgrade:\s*[a-f]/,
    );

    await page.getByRole('button').filter({ hasText: 'RI-RES-UNRESOLVED' }).click();
    const findingDialog = page.getByRole('dialog', { name: /engineering finding/i });
    await expect(findingDialog).toBeVisible();
    await expect(findingDialog).toContainText(fixture.snapshotId!);
    const evidence = findingDialog.getByRole('link');
    const href = await evidence.getAttribute('href');
    expect(href).toContain(`snapshotId=${encodeURIComponent(fixture.snapshotId!)}`);
    expect(href).toContain('factId=');
    await evidence.click();
    await expect(page).toHaveURL(/\/repositories\/.+snapshotId=.+factId=/);
    await expect(page.getByText(/Cited lines \d+.*snapshot/i)).toBeVisible();
    await expect(page.getByText('Verifying evidence...')).toHaveCount(0);
    await expect(page.locator('.monaco-editor')).toBeVisible();
    await page.waitForTimeout(500);

    await capture(page, 'review-supported-finding-evidence', testInfo);
  });

  test('Review no-finding state still marks unassessed categories honestly', async ({ page }, testInfo) => {
    const fixture = byLabel('large-single');
    expect(fixture.reviewFindings).toBe(0);
    await openSurface(page, 'Engineering Review');
    await selectRepository(page, fixture);

    await expect(page.getByRole('heading', { name: 'No evidence-backed findings' })).toBeVisible();
    await expect(page.getByText(/does not mean every engineering category was assessed/i)).toBeVisible();
    await expect(page.getByText('Not assessed', { exact: true }).first()).toBeVisible();
    await capture(page, 'review-no-findings-not-assessed', testInfo);
  });

  test('Insights exposes defined counts, provenance, diagnostics, and unavailable change history', async ({
    page,
  }, testInfo) => {
    const fixture = byLabel('disconnected-unresolved');
    await openSurface(page, 'Insights');
    await selectRepository(page, fixture);

    await expect(page.getByText(fixture.snapshotId!, { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Defined metrics' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'File nodes' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Unresolved relationships' })).toBeVisible();
    await expect(page.getByText('Change-over-time insights are not available yet.')).toBeVisible();
    await expect(page.getByText(/no legacy metadata is used/i)).toBeVisible();
    await expect(page.getByRole('link', { name: 'RI-RES-UNRESOLVED' })).toBeVisible();
    await capture(page, 'insights-defined-metrics', testInfo);
  });

  test('Architecture, Review, and Insights retain the same revision and snapshot identity', async ({ page }) => {
    const fixture = byLabel('small');

    await openSurface(page, 'Architecture');
    await selectRepository(page, fixture);
    await expect(page.getByTestId('revision-manifest')).toContainText(fixture.snapshotId!);
    await page.getByTestId('revision-manifest').getByRole('button', { name: 'Details' }).click();
    await expect(page.getByTestId('revision-manifest')).toContainText(fixture.revisionValue!);

    await openSurface(page, 'Engineering Review');
    await expect(page.getByText(fixture.snapshotId!, { exact: true })).toBeVisible();
    await expect(page.getByText(fixture.revisionValue!, { exact: false })).toBeVisible();

    await openSurface(page, 'Insights');
    await expect(page.getByText(fixture.snapshotId!, { exact: true })).toBeVisible();
    await expect(page.getByText(fixture.revisionValue!, { exact: false })).toBeVisible();
  });

  test('switching repositories clears the previous Review and Insights identity', async ({ page }) => {
    const first = byLabel('disconnected-unresolved');
    const second = byLabel('small');

    await openSurface(page, 'Engineering Review');
    await selectRepository(page, first);
    await expect(page.getByText(first.snapshotId!, { exact: true })).toBeVisible();
    await selectRepository(page, second);
    await expect(page.getByText(first.snapshotId!, { exact: true })).toHaveCount(0);
    await expect(page.getByText(second.snapshotId!, { exact: true })).toBeVisible();

    await openSurface(page, 'Insights');
    await expect(page.getByText(second.snapshotId!, { exact: true })).toBeVisible();
    await selectRepository(page, first);
    await expect(page.getByText(second.snapshotId!, { exact: true })).toHaveCount(0);
    await expect(page.getByText(first.snapshotId!, { exact: true })).toBeVisible();
  });

  test('a second owner receives 404 for another owner’s Review and Insights', async ({ request }) => {
    const email = `prototype-second-owner-${Date.now()}@example.com`;
    const password = 'Second-owner-fixture-2026';
    const registration = await request.post(`${FIXTURES.apiUrl}/auth/register`, {
      data: { email, password },
    });
    expect(registration.status()).toBe(201);
    const accessToken = (await registration.json()).accessToken;
    const repositoryId = byLabel('small').id;

    for (const surface of ['review', 'insights']) {
      const response = await request.get(`${FIXTURES.apiUrl}/analysis/${repositoryId}/${surface}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      expect(response.status(), surface).toBe(404);
      expect((await response.json()).code).toBe('not_found');
    }
  });
});
