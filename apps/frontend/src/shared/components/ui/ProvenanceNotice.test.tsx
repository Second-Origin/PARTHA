import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ProvenanceNotice } from './ProvenanceNotice';

describe('ProvenanceNotice', () => {
  it('discloses the declared limitation for legacy heuristic data', () => {
    render(
      <ProvenanceNotice
        provenance={{ source: 'legacy-heuristic', limitation: 'Derived from declared manifests.' }}
      />,
    );

    expect(screen.getByTestId('provenance-notice')).toBeInTheDocument();
    expect(screen.getByText('Preview')).toBeInTheDocument();
    expect(screen.getByText(/Derived from declared manifests\./)).toBeInTheDocument();
  });

  it('renders nothing for snapshot-backed data', () => {
    const { container } = render(
      <ProvenanceNotice provenance={{ source: 'ri.v1', limitation: null }} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when provenance is absent', () => {
    const { container } = render(<ProvenanceNotice provenance={null} />);

    expect(container).toBeEmptyDOMElement();
  });
});
