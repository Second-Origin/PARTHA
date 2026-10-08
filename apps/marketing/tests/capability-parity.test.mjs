import { URL } from 'node:url';
import { Buffer } from 'node:buffer';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../src/data/sampleAnalysis.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { SAMPLE_FINDINGS, SAMPLE_CATEGORIES } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
test('unsupported demo checks are explicitly proposed and never counted as analyzer findings', () => {
  assert.equal(SAMPLE_FINDINGS.length, 4);
  for (const finding of SAMPLE_FINDINGS) assert.equal(finding.implementation, 'proposed');
  for (const category of SAMPLE_CATEGORIES) assert.equal(category.findingCount, 0);
  const component = readFileSync(new URL('../src/components/DemoModal.tsx', import.meta.url), 'utf8');
  assert.match(component, /Proposed check \(not implemented\)/);
  assert.match(component, /four checks below are proposed and unimplemented/);
});
test('limited categories retain current backend assessment states', () => {
  const backend = readFileSync(new URL('../../backend/app/review/review_service.py', import.meta.url), 'utf8');
  for (const id of ['architecture_boundaries', 'dependency_declarations', 'authentication_evidence', 'repository_structure']) {
    assert.equal(SAMPLE_CATEGORIES.find(category => category.id === id).state, 'partially_assessed');
    assert.match(backend, new RegExp(String.raw`"${id}": \([\s\S]{0,100}"partially_assessed"`));
  }
  assert.equal(SAMPLE_CATEGORIES.find(category => category.id === 'security_vulnerability_scanning').state, 'not_assessed');
});
