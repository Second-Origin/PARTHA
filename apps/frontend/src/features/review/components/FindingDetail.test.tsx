import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ReviewFinding } from '@/shared/types/review';
import { FindingDetail } from './FindingDetail';

const largeFileFinding: ReviewFinding = {
  id: 'large-files',
  title: 'Oversized Source Files',
  category: 'maintainability',
  severity: 'medium',
  status: 'open',
  problem: 'One authored source file exceeds 40 KB. Size is a review signal.',
  impact: 'Review the file with its measured size as context.',
  recommendation: 'Refactor only where responsibilities or complexity warrant it.',
  priority: 3,
  estimatedEffort: 'small',
  affectedFiles: ['/src/application.ts'],
  affectedFileDetails: [{ path: '/src/application.ts', sizeBytes: 72_000 }],
  affectedModules: ['src'],
  tags: ['maintainability'],
};

describe('FindingDetail', () => {
  it('shows the measured size for files with review evidence', () => {
    render(<FindingDetail finding={largeFileFinding} onClose={vi.fn()} />);

    expect(screen.getByText('/src/application.ts (72000 bytes)')).toBeInTheDocument();
  });
});
