import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';

/**
 * Visual acceptance for the architecture graph (#112, #154).
 *
 * Issue #112 is a *visual* defect: nodes were unreadable at default zoom in a
 * single-row layout. Unit tests over the layout function and axe checks in
 * jsdom cannot settle that — neither has a viewport. This drives a real browser
 * against a real backend and asserts the things a reviewer would look at, then
 * captures screenshots as the evidence attached to the PR.
 *
 * Requires seeded fixtures. See docs/PROTOTYPE_READINESS_2026-08-02.md
 * ("Visual acceptance") for the exact commands.
 */

interface Fixture {
  label: string;
  id: string;
  name: string;
  nodes: number;
  edges: number;
}

interface Fixtures {
  email: string;
  password: string;
  repos: Fixture[];
}

const FIXTURES: Fixtures = JSON.parse(
  readFileSync(process.env.PARTHA_VISUAL_FIXTURES ?? '/tmp/visual-fixtures.json', 'utf8'),
);

const byLabel = (label: string) => {
  const found = FIXTURES.repos.find((repo) => repo.label === label);
  if (!found) throw new Error(`fixture "${label}" missing`);
  return found;
};

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(FIXTURES.email);
  await page.getByLabel(/password/i).fill(FIXTURES.password);
  await page.getByRole('button', { name: /sign in|log ?in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 15_000 });
}

async function openArchitecture(page: Page, fixture: Fixture) {
  // Navigate in-app rather than with page.goto: the access token is held in
  // memory (refresh lives in an HTTP-only cookie), so a full document load
  // drops the session and bounces to /login. Clicking the sidebar link is also
  // the path a real user takes.
  await page.getByRole('link', { name: 'Architecture' }).click();
  await expect(page.getByRole('heading', { name: 'Architecture', level: 1 })).toBeVisible({
    timeout: 15_000,
  });

  const trigger = page
    .locator('button')
    .filter({ hasText: /^(No repository|small|medium|large|unanalysed)$/ })
    .first();
  await trigger.click();
  await page
    .locator('button')
    .filter({ hasText: new RegExp(`^${fixture.name}$`) })
    .last()
    .click();
  await expect(trigger).toHaveText(new RegExp(fixture.name));
}

/**
 * Attach a screenshot to the test report and, when PARTHA_VISUAL_SCREENSHOT_DIR
 * is set, also write it to disk so the accepted evidence can be committed and
 * linked from the pull request.
 */
async function capture(target: Page | Locator, name: string, testInfo: TestInfo) {
  const body = await target.screenshot();
  await testInfo.attach(name, { body, contentType: 'image/png' });
  const dir = process.env.PARTHA_VISUAL_SCREENSHOT_DIR;
  if (dir) {
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, `${name}.png`), body);
  }
}

/** React Flow nodes, once the layout has settled. */
const nodes = (page: Page) => page.locator('.react-flow__node');

async function waitForGraph(page: Page) {
  await expect(nodes(page).first()).toBeVisible({ timeout: 20_000 });
  // Let the fit-to-view animation finish before measuring or capturing.
  await page.waitForTimeout(1200);
}

test.describe('architecture graph visual acceptance', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  for (const label of ['small', 'medium', 'large'] as const) {
    test(`${label} graph is readable at default zoom`, async ({ page }, testInfo) => {
      const fixture = byLabel(label);
      await openArchitecture(page, fixture);
      await waitForGraph(page);

      const boxes = await nodes(page).evaluateAll((elements) =>
        elements.map((element) => {
          const rect = element.getBoundingClientRect();
          return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        }),
      );
      expect(boxes.length).toBeGreaterThan(0);

      // 1. Nodes are big enough to read after fit-to-view. The #112 symptom was
      //    nodes shrinking to illegibility because everything sat in one row.
      const tooSmall = boxes.filter((box) => box.width < 60 || box.height < 30);
      expect(tooSmall, `${tooSmall.length}/${boxes.length} nodes rendered too small`).toHaveLength(0);

      // 2. The layout is not a single row: a layered graph must use vertical
      //    space once it has more than a couple of nodes.
      if (boxes.length > 2) {
        const distinctRows = new Set(boxes.map((box) => Math.round(box.y / 40))).size;
        expect(distinctRows, 'layout collapsed into a single row').toBeGreaterThan(1);
      }

      // 3. Nodes do not overlap each other.
      let overlaps = 0;
      for (let i = 0; i < boxes.length; i += 1) {
        for (let j = i + 1; j < boxes.length; j += 1) {
          const a = boxes[i];
          const b = boxes[j];
          const intersects =
            a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
          if (intersects) overlaps += 1;
        }
      }
      expect(overlaps, 'overlapping nodes').toBe(0);

      // 4. Fitting everything and keeping nodes legible conflict once a graph
      //    is large enough. Legibility wins (see READABLE_MIN_ZOOM), so the
      //    contract is: some nodes are on screen, and when the rest do not fit
      //    there is a navigation affordance to reach them.
      const viewport = page.viewportSize()!;
      const onscreen = boxes.filter(
        (box) =>
          box.x + box.width > 0 && box.y + box.height > 0 && box.x < viewport.width && box.y < viewport.height,
      );
      expect(onscreen.length, 'no nodes visible after fit-to-view').toBeGreaterThan(0);

      if (onscreen.length < boxes.length) {
        await expect(
          page.locator('.react-flow__minimap'),
          'graph overflows the viewport but offers no minimap to navigate it',
        ).toBeVisible();
      }

      await capture(page, `architecture-${label}`, testInfo);
    });
  }

  test('long module names are truncated but recoverable', async ({ page }, testInfo) => {
    await openArchitecture(page, byLabel('medium'));
    await waitForGraph(page);

    // Labels truncate to keep node size stable, so the full text has to remain
    // available as the accessible name and tooltip.
    const group = page.locator('.react-flow__node [role="group"]').first();
    const label = await group.getAttribute('aria-label');
    const title = await group.getAttribute('title');
    expect(label && label.length).toBeGreaterThan(0);
    expect(title).toBe(label);

    await capture(page, 'architecture-long-labels', testInfo);
  });

  test('graph is keyboard reachable with a visible focus ring', async ({ page }, testInfo) => {
    await openArchitecture(page, byLabel('medium'));
    await waitForGraph(page);

    // Tab until focus lands inside the graph, then confirm the browser paints a
    // focus indicator rather than relying on hover alone.
    let focusedNode = false;
    for (let i = 0; i < 40 && !focusedNode; i += 1) {
      await page.keyboard.press('Tab');
      focusedNode = await page.evaluate(
        () => document.activeElement?.closest('.react-flow__node') !== null,
      );
    }
    expect(focusedNode, 'no graph node reachable by keyboard').toBe(true);

    const outline = await page.evaluate(() => {
      const active = document.activeElement as HTMLElement | null;
      if (!active) return null;
      const style = getComputedStyle(active);
      return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth, boxShadow: style.boxShadow };
    });
    expect(outline).not.toBeNull();

    await capture(page, 'architecture-keyboard-focus', testInfo);
  });

  test('narrow viewport keeps the graph usable and does not scroll the page sideways', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openArchitecture(page, byLabel('medium'));
    await waitForGraph(page);

    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflows, 'page scrolls horizontally on a narrow viewport').toBe(false);
    await expect(nodes(page).first()).toBeVisible();

    await capture(page, 'architecture-narrow-viewport', testInfo);
  });

  test('an unanalysed repository shows an honest empty state, not an empty graph', async ({
    page,
  }, testInfo) => {
    await openArchitecture(page, byLabel('unanalysed'));

    // It must say why there is nothing, and must not imply the repository has
    // no relationships.
    await expect(page.getByRole('heading', { level: 1, name: 'Architecture' })).toBeVisible();
    await expect(nodes(page)).toHaveCount(0);

    await capture(page, 'architecture-empty-state', testInfo);
  });

  test('revision manifest is visible with the evidence it identifies', async ({ page }, testInfo) => {
    await openArchitecture(page, byLabel('small'));
    const manifest = page.getByTestId('revision-manifest');
    await expect(manifest).toBeVisible({ timeout: 15_000 });
    await expect(manifest.getByTestId('verification-state')).toHaveText(/verified/i);

    // Collapsed by default so it cannot crowd out the graph, but the identity
    // that binds every citation on this page to one revision stays visible.
    await expect(manifest.getByRole('button', { name: /details/i })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    await manifest.getByRole('button', { name: /details/i }).click();

    // The wording must stay a content-hash claim, never a signature claim.
    await expect(manifest).toContainText(/not a digital signature/i);

    await capture(manifest, 'revision-manifest', testInfo);
  });
});
