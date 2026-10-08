import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

const fixtures = JSON.parse(readFileSync(process.env.PARTHA_VISUAL_FIXTURES ?? '/tmp/partha-e2e-fixtures.json', 'utf8'));

test('source explorer renders Monaco without third-party executable or font requests', async ({ page }, testInfo) => {
  const external: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.protocol.startsWith('http') && !['localhost', '127.0.0.1'].includes(url.hostname)) external.push(request.url());
  });
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(fixtures.email);
  await page.getByLabel('Password', {exact:true}).fill(fixtures.password);
  await page.getByRole('button', {name:/sign in|log ?in/i}).click();
  await expect(page.getByRole('heading', {level:1})).toBeVisible();
  const repository = fixtures.repos.find((repo: {label:string}) => repo.label === 'small');
  await page.goto(`/repositories/${repository.id}?tab=Explorer&path=src/api/routes.ts`);
  await expect(page.locator('.monaco-editor')).toBeVisible({timeout:20000});
  await expect(page.locator('.monaco-editor .view-lines')).toContainText('export');
  expect(external).toEqual([]);
  await testInfo.attach('local-editor', {body:await page.screenshot(),contentType:'image/png'});
});
