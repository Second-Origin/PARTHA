import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RequestFlowStep } from '@/shared/types/architecture';
import { RequestFlow } from './RequestFlow';

describe('RequestFlow', () => {
  it('says no flow was observed rather than narrating one that was not (#446)', () => {
    render(<RequestFlow steps={[]} />);

    expect(screen.getByText('No request flow was observed')).toBeInTheDocument();
    // The exact sentence that used to appear on a command-line library.
    expect(screen.queryByText(/Browser or API client sends a request/i)).not.toBeInTheDocument();
    // Absence of an HTTP surface is a property of the repository, not a
    // shortfall in the analysis, and the copy has to say which it is.
    expect(screen.getByText(/it is not a gap in the analysis/i)).toBeInTheDocument();
  });

  it('renders the steps it is given, in order', () => {
    const steps: RequestFlowStep[] = [
      { id: 'client', name: 'Client', type: 'frontend', description: 'A request arrives.', details: [] },
      {
        id: 'api',
        name: 'API Layer',
        type: 'controller',
        description: '1 module classified as route or controller.',
        details: ['orders'],
      },
    ];

    render(<RequestFlow steps={steps} />);

    expect(screen.getByText('Client')).toBeInTheDocument();
    expect(screen.getByText('API Layer')).toBeInTheDocument();
    expect(screen.queryByText('No request flow was observed')).not.toBeInTheDocument();
  });
});
