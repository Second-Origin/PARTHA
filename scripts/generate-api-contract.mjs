import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import openapiTS, { COMMENT_HEADER, astToString } from 'openapi-typescript';

const repoRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const outputPath = resolve(repoRoot, 'apps/frontend/src/shared/services/api/generated.ts');
const checkOnly = process.argv.includes('--check');

function pythonExecutable() {
  if (process.env.PARTHA_PYTHON) return process.env.PARTHA_PYTHON;
  const venvPython = process.platform === 'win32'
    ? resolve(repoRoot, 'apps/backend/.venv/Scripts/python.exe')
    : resolve(repoRoot, 'apps/backend/.venv/bin/python');
  return existsSync(venvPython) ? venvPython : (process.platform === 'win32' ? 'python' : 'python3');
}

function loadOpenApiDocument() {
  const result = spawnSync(
    pythonExecutable(),
    ['-c', 'import json; from app.main import app; print(json.dumps(app.openapi(), separators=(",", ":")))'],
    { cwd: resolve(repoRoot, 'apps/backend'), encoding: 'utf8' },
  );

  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`Backend OpenAPI generation failed:\n${result.stderr || result.stdout}`);
  }
  const document = JSON.parse(result.stdout);
  stripDynamicDefaults(document);
  return document;
}

// Pydantic evaluates datetime defaults while importing the backend module.
// Those values are runtime metadata, not part of the TypeScript contract, and
// must not make two generations from the same source differ.
function stripDynamicDefaults(value) {
  if (!value || typeof value !== 'object') return;
  if (Array.isArray(value)) {
    value.forEach(stripDynamicDefaults);
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    if (key === 'default' && typeof child === 'string' && /^\d{4}-\d{2}-\d{2}T.*Z$/.test(child)) {
      delete value[key];
    } else {
      stripDynamicDefaults(child);
    }
  }
}

function assertSafeGeneratedOutput(content) {
  const environmentUrl = /https?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal)(?::\d+)?/i;
  const embeddedSecret = /(?:api[_-]?key|password|secret|token)\s*[:=]\s*["'`][^"'`]+["'`]/i;
  if (environmentUrl.test(content)) {
    throw new Error('Generated API contract contains an environment-specific URL.');
  }
  if (embeddedSecret.test(content)) {
    throw new Error('Generated API contract contains an embedded secret-like value.');
  }
}

const document = loadOpenApiDocument();
const generated = `${COMMENT_HEADER}// Source: apps/backend/app.main:app.openapi()\n// Generator: openapi-typescript@7.13.0\n\n${astToString(await openapiTS(document, { alphabetize: true }))}\n`;
assertSafeGeneratedOutput(generated);

if (checkOnly) {
  if (!existsSync(outputPath)) throw new Error(`Generated contract is missing: ${outputPath}`);
  const current = readFileSync(outputPath, 'utf8');
  if (current !== generated) {
    const firstDifference = [...generated].findIndex((character, index) => current[index] !== character);
    throw new Error(`Generated API contract is stale at character ${firstDifference}. Run \`npm run generate:api-contract\`.`);
  }
  console.log(`API contract is up to date: ${outputPath}`);
} else {
  writeFileSync(outputPath, generated, 'utf8');
  console.log(`Generated API contract: ${outputPath}`);
}
