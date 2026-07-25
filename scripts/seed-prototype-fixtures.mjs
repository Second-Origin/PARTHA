import { execFile } from 'node:child_process';
import { chmod, mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const apiUrl = (process.env.PARTHA_FIXTURE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
const outputPath = process.env.PARTHA_VISUAL_FIXTURES ?? join(tmpdir(), 'partha-prototype-fixtures.json');
const email = 'prototype-fixture@example.com';
const password = 'Prototype-fixture-2026';

const moduleSource = (name, imports = []) => [
  ...imports.map((target) => `import { value as dependency } from '${target}';`),
  `export const value = '${name}';`,
  `export function ${name.replace(/[^a-zA-Z0-9]/g, '') || 'fixture'}() { return ${
    imports.length ? 'dependency' : 'value'
  }; }`,
  '',
].join('\n');

const FIXTURES = [
  {
    label: 'small',
    files: {
      'package.json': '{"name":"fixture-small","dependencies":{"react":"18.3.1"}}',
      'src/api/routes.ts': moduleSource('Routes', ['../services/user-service']),
      'src/services/user-service.ts': moduleSource('UserService', ['../models/user']),
      'src/models/user.ts': 'export interface User { id: string; }\nexport const value = "user";\n',
      'src/repositories/user-repository.ts': moduleSource('UserRepository', ['../models/user']),
      'README.md': '# Small snapshot-backed fixture\n',
    },
  },
  {
    label: 'medium',
    files: {
      'package.json': '{"name":"fixture-medium","dependencies":{"react":"18.3.1","zod":"3.23.8"}}',
      'src/api/account-routes.ts': moduleSource('AccountRoutes', ['../services/account-service']),
      'src/api/billing-routes.ts': moduleSource('BillingRoutes', ['../services/billing-service']),
      'src/services/account-service.ts': moduleSource('AccountService', ['../models/account']),
      'src/services/billing-service.ts': moduleSource('BillingService', ['../repositories/billing-repository']),
      'src/models/account.ts': 'export interface Account { id: string; }\nexport const value = "account";\n',
      'src/repositories/billing-repository.ts': moduleSource('BillingRepository', ['../models/account']),
      'src/middleware/auth-middleware.ts': moduleSource('AuthMiddleware'),
      'src/config/settings.ts': moduleSource('Settings'),
      'src/lib/date.ts': moduleSource('DateUtility'),
      'README.md': '# Medium multi-layer fixture\n',
    },
  },
  {
    label: 'large-multi',
    files: Object.fromEntries([
      ['package.json', '{"name":"fixture-large-multi","dependencies":{"react":"18.3.1","zod":"3.23.8"}}'],
      ...Array.from({ length: 4 }, (_, index) => [
        `src/api/feature-${index + 1}-routes.ts`,
        moduleSource(`Feature${index + 1}Routes`, [`../services/feature-${index + 1}-service`]),
      ]),
      ...Array.from({ length: 4 }, (_, index) => [
        `src/services/feature-${index + 1}-service.ts`,
        moduleSource(`Feature${index + 1}Service`, [`../repositories/feature-${index + 1}-repository`]),
      ]),
      ...Array.from({ length: 4 }, (_, index) => [
        `src/repositories/feature-${index + 1}-repository.ts`,
        moduleSource(`Feature${index + 1}Repository`, [`../models/feature-${index + 1}-model`]),
      ]),
      ...Array.from({ length: 4 }, (_, index) => [
        `src/models/feature-${index + 1}-model.ts`,
        `export interface Feature${index + 1}Model { id: string; }\nexport const value = "model-${index + 1}";\n`,
      ]),
      ['src/middleware/request-middleware.ts', moduleSource('RequestMiddleware')],
      ['src/config/runtime-settings.ts', moduleSource('RuntimeSettings')],
      ['src/lib/telemetry-util.ts', moduleSource('TelemetryUtil')],
      ['README.md', '# Large multi-layer fixture\n'],
    ]),
  },
  {
    label: 'large-single',
    expectedNodes: 14,
    files: Object.fromEntries([
      ['package.json', '{"name":"fixture-large-single"}'],
      ...Array.from({ length: 13 }, (_, index) => {
        const current = String(index + 1).padStart(2, '0');
        const next = String(((index + 1) % 13) + 1).padStart(2, '0');
        return [
          `src/segment-${current}/component.ts`,
          moduleSource(`Segment${current}`, [`../segment-${next}/component`]),
        ];
      }),
      ['README.md', '# Fourteen modules intentionally sharing one semantic layer\n'],
    ]),
  },
  {
    label: 'long-labels',
    files: {
      'package.json': '{"name":"fixture-long-labels"}',
      'src/customer-subscription-entitlement-orchestration/component.ts': moduleSource(
        'CustomerSubscriptionEntitlementOrchestration',
        ['../international-payment-reconciliation-and-settlement/component'],
      ),
      'src/international-payment-reconciliation-and-settlement/component.ts': moduleSource(
        'InternationalPaymentReconciliationAndSettlement',
      ),
      'src/regulatory-compliance-reporting-and-audit/component.ts': moduleSource(
        'RegulatoryComplianceReportingAndAudit',
      ),
      'README.md': '# Long labels remain recoverable through accessible names\n',
    },
  },
  {
    label: 'disconnected-unresolved',
    files: {
      'package.json': '{"name":"fixture-disconnected-unresolved"}',
      'src/api/orphan-routes.ts': moduleSource('OrphanRoutes', ['../services/missing-service']),
      'src/services/connected-service.ts': moduleSource('ConnectedService', ['../models/record']),
      'src/models/record.ts': 'export interface Record { id: string; }\nexport const value = "record";\n',
      'src/isolated/reporting-component.ts': moduleSource('IsolatedReportingComponent'),
      'README.md': '# Unresolved and disconnected evidence fixture\n',
    },
  },
  {
    label: 'unanalysed',
    analyse: false,
    files: {
      'package.json': '{"name":"fixture-unanalysed"}',
      'src/component.ts': moduleSource('UnanalysedComponent'),
      'README.md': '# Deliberately not analysed\n',
    },
  },
];

async function api(path, { token, method = 'GET', body, expected } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${apiUrl}${path}`, {
    method,
    headers,
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (expected ? !expected.includes(response.status) : !response.ok) {
    throw new Error(`${method} ${path} returned ${response.status}: ${JSON.stringify(payload)}`);
  }
  return { status: response.status, payload };
}

async function authenticate() {
  const registration = await api('/auth/register', {
    method: 'POST',
    body: { email, password },
    expected: [201, 409],
  });
  if (registration.status === 201) return registration.payload.accessToken;
  const login = await api('/auth/login', { method: 'POST', body: { email, password } });
  return login.payload.accessToken;
}

async function archiveFixture(root, fixture) {
  const sourceDir = join(root, fixture.label);
  await mkdir(sourceDir, { recursive: true });
  for (const [path, content] of Object.entries(fixture.files)) {
    const fullPath = join(sourceDir, path);
    await mkdir(dirname(fullPath), { recursive: true });
    await writeFile(fullPath, content, 'utf8');
  }
  const archivePath = join(root, `${fixture.label}.zip`);
  await execFileAsync('zip', ['-qr', archivePath, '.'], { cwd: sourceDir });
  return archivePath;
}

async function upload(token, fixture, archivePath) {
  const data = new FormData();
  const archive = await import('node:fs').then(({ readFileSync }) => readFileSync(archivePath));
  data.append('file', new Blob([archive], { type: 'application/zip' }), basename(archivePath));
  return (await api('/repositories/upload', { token, method: 'POST', body: data })).payload;
}

async function waitForAnalysis(token, repositoryId) {
  await api(`/analysis/${repositoryId}/start`, { token, method: 'POST' });
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const { payload } = await api(`/analysis/${repositoryId}/status`, { token });
    if (payload.status === 'completed') return;
    if (payload.status === 'failed' || payload.status === 'cancelled') {
      throw new Error(`analysis ${repositoryId} ended as ${payload.status}: ${payload.error ?? ''}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`analysis ${repositoryId} did not complete within 120 seconds`);
}

async function main() {
  const token = await authenticate();
  const existing = (await api('/repositories', { token })).payload.data;
  for (const repository of existing) {
    await api(`/repositories/${repository.id}`, { token, method: 'DELETE' });
  }

  const workingRoot = await mkdtemp(join(tmpdir(), 'partha-prototype-fixtures-'));
  const repositories = [];
  try {
    for (const fixture of FIXTURES) {
      const archivePath = await archiveFixture(workingRoot, fixture);
      const repository = await upload(token, fixture, archivePath);
      if (fixture.analyse !== false) await waitForAnalysis(token, repository.id);

      let architecture = { nodes: [], edges: [], relationshipSnapshotId: null };
      let review = { findings: [], snapshotId: null };
      if (fixture.analyse !== false) {
        architecture = (await api(`/analysis/${repository.id}/architecture`, { token })).payload;
        review = (await api(`/analysis/${repository.id}/review`, { token })).payload;
      }
      if (fixture.expectedNodes !== undefined && architecture.nodes.length !== fixture.expectedNodes) {
        throw new Error(
          `${fixture.label} produced ${architecture.nodes.length} architecture nodes; expected ${fixture.expectedNodes}`,
        );
      }
      repositories.push({
        label: fixture.label,
        id: repository.id,
        name: repository.name,
        revisionValue: repository.revision?.value ?? null,
        snapshotId: architecture.relationshipSnapshotId,
        nodes: architecture.nodes.length,
        edges: architecture.edges.length,
        reviewFindings: review.findings.length,
      });
    }

    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(
      outputPath,
      `${JSON.stringify({ schemaVersion: 'prototype-fixtures.v1', apiUrl, email, password, repos: repositories }, null, 2)}\n`,
      { encoding: 'utf8', mode: 0o600 },
    );
    await chmod(outputPath, 0o600);
  } finally {
    await rm(workingRoot, { recursive: true, force: true });
  }

  process.stdout.write(`Seeded ${repositories.length} disposable prototype repositories. Fixture manifest: ${outputPath}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
});
