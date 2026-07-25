import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RepositorySource } from '@/shared/types';
import { DataSourceBadge } from './DataSourceBadge';

describe('DataSourceBadge', () => {
  it('shows actual repository provenance instead of a generic real-data claim', () => {
    const { rerender } = render(<DataSourceBadge source="upload" />);

    expect(screen.getByTestId('repository-source')).toHaveTextContent('Uploaded archive');
    expect(screen.queryByText('Real data')).not.toBeInTheDocument();

    rerender(<DataSourceBadge source="github" />);
    expect(screen.getByTestId('repository-source')).toHaveTextContent('GitHub repository');
  });

  it('renders nothing when provenance is unavailable', () => {
    const { container } = render(<DataSourceBadge source={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('fails closed for an origin value without a label', () => {
    const { container } = render(
      <DataSourceBadge source={'gitlab' as unknown as RepositorySource} />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
