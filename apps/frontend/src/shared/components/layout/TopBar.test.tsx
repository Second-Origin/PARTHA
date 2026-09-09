import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { TopBar } from './TopBar';

const initialAppState = useAppStore.getState();

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({
    repositories: [],
    activeRepository: null,
    selectRepository: () => undefined,
  }),
}));

function renderTopBar() {
  return render(
    <MemoryRouter>
      <TopBar />
    </MemoryRouter>,
  );
}

describe('TopBar icon-only controls (#236)', () => {
  beforeEach(() => {
    useAppStore.setState({ ...initialAppState, notifications: [] });
  });

  afterEach(() => {
    useAppStore.setState(initialAppState);
  });

  it('gives the notification control a stable accessible name', () => {
    renderTopBar();

    const trigger = screen.getByTestId('notification-menu-trigger');
    expect(trigger).toHaveAccessibleName('Notifications');
    // The bell glyph is purely decorative -- the accessible name comes from
    // aria-label, not from screen-reader-visible icon content.
    expect(trigger.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('reflects unread notifications in the accessible name', () => {
    useAppStore.setState({
      notifications: [
        {
          id: '1',
          title: 'Analysis complete',
          message: 'done',
          type: 'success',
          read: false,
          createdAt: new Date().toISOString(),
        },
      ],
    });
    renderTopBar();

    expect(screen.getByTestId('notification-menu-trigger')).toHaveAccessibleName('Notifications, 1 unread');
  });

  it('gives the account control a stable accessible name', () => {
    renderTopBar();

    const trigger = screen.getByTestId('user-menu-trigger');
    expect(trigger).toHaveAccessibleName('Account menu');
    expect(trigger.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('still opens the account menu on click (behavior unchanged)', () => {
    renderTopBar();

    fireEvent.click(screen.getByTestId('user-menu-trigger'));

    expect(screen.getByRole('button', { name: /Sign Out/ })).toBeInTheDocument();
  });
});
