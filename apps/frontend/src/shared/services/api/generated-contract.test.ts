import { describe, expect, it } from 'vitest';
import type { components, paths } from './generated';
import generated from './generated.ts?raw';

// These type aliases make the proof-workflow fields compile against the
// generated document, so a schema rename/removal fails the frontend build.
type ProofWorkflowContract = Pick<
  components['schemas']['RiSnapshotMetadataResponse'],
  'schemaVersion' | 'snapshotId' | 'revisionValue' | 'canonicalGraphHash' | 'sealedAt'
> & Pick<
  components['schemas']['EvidenceSourceResponse'],
  'factId' | 'path' | 'startLine' | 'endLine' | 'status' | 'content'
> & Pick<
  components['schemas']['ArchitectureDiagnostic'],
  'code' | 'severity' | 'message' | 'path' | 'startLine' | 'endLine'
>;

type ErrorEnvelope = Pick<components['schemas']['ErrorResponse'], 'code' | 'message' | 'details' | 'request_id'>;
type ReviewOperation = paths['/analysis/{repository_id}/review']['get'];
type ReviewResponse = NonNullable<ReviewOperation['responses']['200']['content']>['application/json'];

// Exported solely so the compiler checks the selected generated component
// fields and the response operation above under strict TypeScript settings.
export type GeneratedContractCoverage = ProofWorkflowContract & ErrorEnvelope & ReviewResponse;

describe('generated frontend API contract', () => {
  it('contains proof-workflow, diagnostics, and error-envelope schemas', () => {
    expect(generated).toContain('RiSnapshotMetadataResponse');
    expect(generated).toContain('EvidenceSourceResponse');
    expect(generated).toContain('ArchitectureDiagnostic');
    expect(generated).toContain('EngineeringReviewResponse');
    expect(generated).toContain('ErrorResponse');
    expect(generated).toContain('canonicalGraphHash');
    expect(generated).toContain('request_id');
  });

  it('contains no environment URLs or embedded secret-like values', () => {
    expect(generated).not.toMatch(/https?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal)/i);
    expect(generated).not.toMatch(/(?:api[_-]?key|password|secret|token)\s*[:=]\s*["'`][^"'`]+["'`]/i);
  });
});
