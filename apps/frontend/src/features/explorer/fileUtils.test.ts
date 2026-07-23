import { describe, expect, it } from 'vitest';
import { parseEvidenceCitation } from './fileUtils';

function params(entries: Record<string, string>): URLSearchParams {
  return new URLSearchParams({ factId: 'fact_1', ...entries });
}

describe('parseEvidenceCitation', () => {
  it('parses a fully valid citation', () => {
    expect(
      parseEvidenceCitation(
        params({ path: 'src/routes.py', startLine: '6', endLine: '7', snapshotId: 'snap_1' }),
      ),
    ).toEqual({ path: 'src/routes.py', startLine: 6, endLine: 7, snapshotId: 'snap_1', factId: 'fact_1' });
  });

  it('allows a single-line span (start === end)', () => {
    const result = parseEvidenceCitation(
      params({ path: 'src/routes.py', startLine: '10', endLine: '10', snapshotId: 'snap_1' }),
    );
    expect(result).toEqual({
      path: 'src/routes.py',
      startLine: 10,
      endLine: 10,
      snapshotId: 'snap_1',
      factId: 'fact_1',
    });
  });

  it('returns null when a required param is missing', () => {
    expect(parseEvidenceCitation(params({ startLine: '1', endLine: '1', snapshotId: 'snap_1' }))).toBeNull();
    expect(parseEvidenceCitation(params({ path: 'a.py', endLine: '1', snapshotId: 'snap_1' }))).toBeNull();
    expect(parseEvidenceCitation(params({ path: 'a.py', startLine: '1', snapshotId: 'snap_1' }))).toBeNull();
    expect(parseEvidenceCitation(params({ path: 'a.py', startLine: '1', endLine: '1' }))).toBeNull();
    const missingFactId = params({ path: 'a.py', startLine: '1', endLine: '1', snapshotId: 'snap_1' });
    missingFactId.delete('factId');
    expect(parseEvidenceCitation(missingFactId)).toBeNull();
  });

  it('returns null for non-integer line numbers instead of NaN', () => {
    const malformed = parseEvidenceCitation(
      params({ path: 'a.py', startLine: 'not-a-number', endLine: '1', snapshotId: 'snap_1' }),
    );
    expect(malformed).toBeNull();
  });

  it('returns null for a decimal line number', () => {
    expect(
      parseEvidenceCitation(params({ path: 'a.py', startLine: '1.5', endLine: '2', snapshotId: 'snap_1' })),
    ).toBeNull();
  });

  it('returns null for zero or negative line numbers', () => {
    expect(
      parseEvidenceCitation(params({ path: 'a.py', startLine: '0', endLine: '1', snapshotId: 'snap_1' })),
    ).toBeNull();
    expect(
      parseEvidenceCitation(params({ path: 'a.py', startLine: '-1', endLine: '1', snapshotId: 'snap_1' })),
    ).toBeNull();
  });

  it('returns null when endLine is before startLine', () => {
    expect(
      parseEvidenceCitation(params({ path: 'a.py', startLine: '10', endLine: '2', snapshotId: 'snap_1' })),
    ).toBeNull();
  });

  it('returns null for an empty snapshotId or path', () => {
    expect(
      parseEvidenceCitation(params({ path: '', startLine: '1', endLine: '1', snapshotId: 'snap_1' })),
    ).toBeNull();
    expect(
      parseEvidenceCitation(params({ path: 'a.py', startLine: '1', endLine: '1', snapshotId: '' })),
    ).toBeNull();
    expect(
      parseEvidenceCitation(
        params({ path: 'a.py', startLine: '1', endLine: '1', snapshotId: 'snap_1', factId: '' }),
      ),
    ).toBeNull();
  });

  it('returns null for injected/oversized garbage instead of throwing', () => {
    expect(
      parseEvidenceCitation(
        params({ path: 'a.py', startLine: '1e300', endLine: '1', snapshotId: 'snap_1' }),
      ),
    ).toBeNull();
    expect(() =>
      parseEvidenceCitation(params({ path: 'a.py', startLine: '<script>', endLine: '1', snapshotId: 'snap_1' })),
    ).not.toThrow();
  });
});
