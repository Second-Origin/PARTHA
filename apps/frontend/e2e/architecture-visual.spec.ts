import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';

interface Fixture {
  label: string;
  id: string;
  name: string;
  revisionValue: string | null;
  snapshotId: string | null;
  nodes: number;
  edges: number;
  reviewFindings: number;
}

interface Fixtures {
  email: string;
  password: string;
  repos: Fixture[];
}

const FIXTURES: Fixtures = JSON.parse(
  readFileSync(process.env.PARTHA_VISUAL_FIXTURES ?? '/tmp/partha-prototype-fixtures.json', 'utf8'),
);

const byLabel = (label: string) => {
  const fixture = FIXTURES.repos.find((repository) => repository.label === label);
  if (!fixture) throw new Error(`fixture "${label}" missing`);
  return fixture;
};

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(FIXTURES.email);
  await page.getByLabel(/password/i).fill(FIXTURES.password);
  await page.getByRole('button', { name: /sign in|log ?in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 });
}

async function openPrimaryNavigation(page: Page) {
  if ((page.viewportSize()?.width ?? 1440) < 768) {
    await page.getByRole('button', { name: 'Open navigation drawer' }).click();
    await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  }
}

async function openSurface(page: Page, name: string) {
  await openPrimaryNavigation(page);
  await page.getByRole('link', { name, exact: true }).click();
}

async function selectRepository(page: Page, fixture: Fixture) {
  const trigger = page.locator('header button').filter({
    hasText: /^(No repository|small|medium|large-multi|large-single|long-labels|disconnected-unresolved|unanalysed)$/,
  }).first();
  await trigger.click();
  await page.locator('button').filter({ hasText: new RegExp(`^${fixture.name}$`) }).last().click();
  await expect(trigger).toHaveText(fixture.name);
}

async function openArchitecture(page: Page, fixture: Fixture) {
  await openSurface(page, 'Architecture');
  await expect(page.getByRole('heading', { name: 'Architecture', level: 1 })).toBeVisible({
    timeout: 15_000,
  });
  await selectRepository(page, fixture);
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

const graphNodes = (page: Page) => page.locator('.react-flow__node');

async function waitForGraph(page: Page) {
  await expect(graphNodes(page).first()).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(500);
}

async function nodeMeasurements(page: Page) {
  return graphNodes(page).evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      const label = element.querySelector<HTMLElement>('[data-testid="architecture-node-label"]');
      const labelStyle = label ? getComputedStyle(label) : null;
      const scale = rect.width / 220;
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        label: label?.textContent?.trim() ?? '',
        effectiveFontSize: Number.parseFloat(labelStyle?.fontSize ?? '0') * scale,
      };
    }),
  );
}

function overlapCount(boxes: Awaited<ReturnType<typeof nodeMeasurements>>) {
  let overlaps = 0;
  for (let left = 0; left < boxes.length; left += 1) {
    for (let right = left + 1; right < boxes.length; right += 1) {
      const a = boxes[left];
      const b = boxes[right];
      if (
        a.x < b.x + b.width
        && a.x + a.width > b.x
        && a.y < b.y + b.height
        && a.y + a.height > b.y
      ) overlaps += 1;
    }
  }
  return overlaps;
}

test.describe('architecture graph visual acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  for (const label of ['small', 'medium', 'large-multi', 'large-single'] as const) {
    test(`${label} graph is readable at its default view`, async ({ page }, testInfo) => {
      const fixture = byLabel(label);
      await openArchitecture(page, fixture);
      await waitForGraph(page);

      const boxes = await nodeMeasurements(page);
      expect(boxes).toHaveLength(fixture.nodes);
      expect(boxes.every((box) => box.label.length > 0), 'a visible graph node has no label').toBe(true);
      expect(
        boxes.filter((box) => box.width < 180 || box.height < 85),
        'node geometry fell below the readable 0.85x floor',
      ).toHaveLength(0);
      expect(
        boxes.filter((box) => box.effectiveFontSize < 10),
        'a node label renders below 10 CSS pixels after graph scaling',
      ).toHaveLength(0);
      expect(overlapCount(boxes), 'graph nodes overlap').toBe(0);

      const graphBounds = await page.locator('.react-flow').boundingBox();
      expect(graphBounds).not.toBeNull();
      const clipped = boxes.filter(
        (box) =>
          box.x < graphBounds!.x - 1
          || box.y < graphBounds!.y - 1
          || box.x + box.width > graphBounds!.x + graphBounds!.width + 1
          || box.y + box.height > graphBounds!.y + graphBounds!.height + 1,
      );
      expect(clipped, 'the default view partially clips a graph node').toHaveLength(0);

      const distinctColumns = new Set(boxes.map((box) => Math.round(box.x / 40))).size;
      const distinctRows = new Set(boxes.map((box) => Math.round(box.y / 40))).size;
      if (label === 'large-single') {
        expect(distinctColumns, 'busy single semantic layer did not wrap into subcolumns').toBeGreaterThan(1);
        expect(distinctRows, 'busy single semantic layer stayed in one row').toBeGreaterThan(1);
      } else if (boxes.length > 2) {
        expect(distinctColumns).toBeGreaterThan(1);
        expect(distinctRows).toBeGreaterThan(1);
      }

      if (label === 'small') {
        const labels = boxes.map((box) => box.label);
        expect(labels).toEqual(expect.arrayContaining(['Api', 'Services', 'Domain', 'Repositories']));
      }

      const viewport = page.viewportSize()!;
      const visible = boxes.filter(
        (box) =>
          box.x + box.width > 0
          && box.y + box.height > 0
          && box.x < viewport.width
          && box.y < viewport.height,
      );
      expect(visible.length, 'the default view contains no graph nodes').toBeGreaterThan(0);
      if (visible.length < boxes.length) await expect(page.locator('.react-flow__minimap')).toBeVisible();

      await capture(page, `architecture-${label}`, testInfo);
    });
  }

  test('long module names are truncated visually and recoverable accessibly', async ({ page }, testInfo) => {
    await openArchitecture(page, byLabel('long-labels'));
    await waitForGraph(page);

    const group = page.locator('.react-flow__node [role="group"]').first();
    const accessibleName = await group.getAttribute('aria-label');
    expect(accessibleName).toContain('Customer Subscription Entitlement Orchestration');
    expect(await group.getAttribute('title')).toBe(accessibleName);
    await capture(page, 'architecture-long-labels', testInfo);
  });

  test('focused nodes remain visible, have a real focus ring, and open with the keyboard', async ({
    page,
  }, testInfo) => {
    await openArchitecture(page, byLabel('medium'));
    await waitForGraph(page);

    let reachedNode = false;
    for (let index = 0; index < 50 && !reachedNode; index += 1) {
      await page.keyboard.press('Tab');
      reachedNode = await page.evaluate(() => document.activeElement?.closest('.react-flow__node') !== null);
    }
    expect(reachedNode, 'no graph node is reachable by Tab').toBe(true);

    const focusState = await page.evaluate(() => {
      const node = document.activeElement?.closest<HTMLElement>('.react-flow__node');
      if (!node) return null;
      const style = getComputedStyle(node);
      const box = node.getBoundingClientRect();
      return {
        outlineStyle: style.outlineStyle,
        outlineWidth: Number.parseFloat(style.outlineWidth),
        boxShadow: style.boxShadow,
        fullyVisible:
          box.left >= 0
          && box.top >= 0
          && box.right <= document.documentElement.clientWidth
          && box.bottom <= document.documentElement.clientHeight,
      };
    });
    expect(focusState?.fullyVisible).toBe(true);
    expect(
      (focusState?.outlineStyle === 'solid' && (focusState?.outlineWidth ?? 0) >= 2)
        || focusState?.boxShadow !== 'none',
      'focused graph node has no browser-painted indicator',
    ).toBe(true);
    await capture(page, 'architecture-keyboard-focus', testInfo);

    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: /architecture node/i })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: /architecture node/i })).toHaveCount(0);

    await page.keyboard.press('Space');
    await expect(page.getByRole('dialog', { name: /architecture node/i })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: /architecture node/i })).toHaveCount(0);
  });

  test('fit and reset preserve readable node geometry', async ({ page }) => {
    await openArchitecture(page, byLabel('large-single'));
    await waitForGraph(page);
    const initial = await nodeMeasurements(page);

    await page.getByRole('button', { name: 'Fit View' }).click();
    await page.waitForTimeout(400);
    const fitted = await nodeMeasurements(page);
    await page.getByRole('button', { name: 'Reset Layout' }).click();
    await page.waitForTimeout(500);
    const reset = await nodeMeasurements(page);

    for (const boxes of [fitted, reset]) {
      expect(boxes.filter((box) => box.width < 180 || box.height < 85)).toHaveLength(0);
      expect(overlapCount(boxes)).toBe(0);
    }
    expect(reset.map((box) => box.label)).toEqual(initial.map((box) => box.label));
  });

  test('narrow viewport keeps navigation, graph, toolbar, and minimap reachable', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openArchitecture(page, byLabel('medium'));
    await waitForGraph(page);

    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      ),
      'page scrolls horizontally on a narrow viewport',
    ).toBe(false);
    const completeNodes = (await nodeMeasurements(page)).filter(
      (box) => box.x >= 0 && box.y >= 0 && box.x + box.width <= 390 && box.y + box.height <= 844,
    );
    expect(completeNodes.length, 'no complete architecture node is visible on mobile').toBeGreaterThan(0);
    await expect(page.getByRole('button', { name: 'Fit View' })).toBeVisible();
    await expect(page.locator('.react-flow__minimap')).toBeVisible();

    const openButton = page.getByRole('button', { name: 'Open navigation drawer' });
    await openButton.click();
    const navigation = page.getByRole('navigation', { name: 'Primary navigation' });
    await expect(navigation).toBeVisible();
    expect(await page.evaluate(() => document.activeElement?.getAttribute('aria-label'))).toBe(
      'Close navigation drawer',
    );
    await page.keyboard.press('Escape');
    await expect(navigation).not.toBeInViewport();
    await expect(openButton).toBeFocused();

    await capture(page, 'architecture-narrow-viewport', testInfo);
  });

  test('unanalysed repository has an honest empty state', async ({ page }, testInfo) => {
    await openArchitecture(page, byLabel('unanalysed'));
    await expect(graphNodes(page)).toHaveCount(0);
    await expect(page.getByText(/analysis|analysed|sealed snapshot/i).first()).toBeVisible();
    await capture(page, 'architecture-empty-state', testInfo);
  });

  test('revision manifest exposes verifiable snapshot identity without a signature claim', async ({
    page,
  }, testInfo) => {
    await openArchitecture(page, byLabel('small'));
    const manifest = page.getByTestId('revision-manifest');
    await expect(manifest).toBeVisible({ timeout: 15_000 });
    await expect(manifest.getByTestId('verification-state')).toHaveText(/verified/i);
    await expect(manifest).toContainText(byLabel('small').snapshotId!);
    await manifest.getByRole('button', { name: /details/i }).click();
    await expect(manifest).toContainText(/not a digital signature/i);
    await capture(manifest, 'revision-manifest', testInfo);
  });
});
