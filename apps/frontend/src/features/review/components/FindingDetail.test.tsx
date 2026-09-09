import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ReviewFinding } from '@/shared/types/review';
import { FindingDetail } from './FindingDetail';

const finding: ReviewFinding = {
  id: 'finding:1',
  category: 'relationship_resolution',
  severity: 'medium',
  title: 'Unresolved relationship',
  explanation: 'The imported name did not resolve to a stored target.',
  path: 'src/index.ts',
  startLine: 1,
  endLine: 1,
  snapshotId: 'snap-1',
  factId: 'observation-1',
  evidenceId: 'evidence-1',
  extractorName: 'typescript-extractor',
  extractorVersion: '1.0.0',
  diagnosticCode: 'RI-RES-UNRESOLVED',
  ruleId: 'engineering-review.v2/RI-RES-UNRESOLVED',
  remediationGuidance: 'Make the target explicit.',
  supportStatus: 'supported',
  provenance: {
    source: 'ri.v1',
    snapshotId: 'snap-1',
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: 'sha256:abc',
  },
  evidence: {
    evidenceId: 'evidence-1',
    snapshotId: 'snap-1',
    factId: 'observation-1',
    path: 'src/index.ts',
    startLine: 1,
    endLine: 1,
    extractorName: 'typescript-extractor',
    extractorVersion: '1.0.0',
  },
};

describe('FindingDetail', () => {
  it('shows authentic evidence and closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <FindingDetail repositoryId="repo-1" finding={finding} onClose={onClose} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('dialog', { name: /unresolved relationship/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /src\/index\.ts:1/i })).toHaveAttribute(
      'href',
      expect.stringContaining('snapshotId=snap-1'),
    );
    expect(screen.queryByText(/AI-powered/i)).not.toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
