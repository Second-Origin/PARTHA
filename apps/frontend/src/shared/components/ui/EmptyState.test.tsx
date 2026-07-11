import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Inbox } from 'lucide-react';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('renders the title and description', () => {
    render(<EmptyState icon={Inbox} title="No repositories" description="Import one to get started." />);

    expect(screen.getByText('No repositories')).toBeInTheDocument();
    expect(screen.getByText('Import one to get started.')).toBeInTheDocument();
  });

  it('renders no button when no action is given', () => {
    render(<EmptyState icon={Inbox} title="Empty" description="Nothing here." />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('fires the action callback from the button', () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        icon={Inbox}
        title="Empty"
        description="Nothing here."
        action={{ label: 'Import repository', onClick }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Import repository' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
