import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { waitlistService } from '@/shared/services/api';
import { ApiError } from '@/shared/services/api';
import { WaitlistModal } from './WaitlistModal';

describe('WaitlistModal', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('submits the entered email and optional name, then shows a confirmation', async () => {
    const join = vi.spyOn(waitlistService, 'join').mockResolvedValue({ status: 'ok' });
    const onClose = vi.fn();

    render(<WaitlistModal onClose={onClose} />);

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'visitor@example.com' } });
    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: 'Visitor Name' } });
    fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }));

    await waitFor(() =>
      expect(join).toHaveBeenCalledWith({ email: 'visitor@example.com', name: 'Visitor Name' }),
    );
    expect(await screen.findByText("You're on the list")).toBeVisible();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('submits without a name when the optional field is left blank', async () => {
    const join = vi.spyOn(waitlistService, 'join').mockResolvedValue({ status: 'ok' });

    render(<WaitlistModal onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'no-name@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }));

    await waitFor(() => expect(join).toHaveBeenCalledWith({ email: 'no-name@example.com', name: undefined }));
  });

  it('shows an error and does not confirm when the request fails', async () => {
    vi.spyOn(waitlistService, 'join').mockRejectedValue(
      new ApiError(422, 'Request validation failed.', null, '/waitlist'),
    );

    render(<WaitlistModal onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'rejected@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }));

    expect(await screen.findByRole('alert')).toBeVisible();
    expect(screen.queryByText("You're on the list")).not.toBeInTheDocument();
  });

  it('calls onClose when Close is clicked before submitting', () => {
    const onClose = vi.fn();
    render(<WaitlistModal onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
