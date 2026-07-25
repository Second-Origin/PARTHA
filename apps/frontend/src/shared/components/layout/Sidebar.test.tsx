import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { useAuthStore } from '@/app/store/useAuthStore';
import { Sidebar } from './Sidebar';

const initialAppState = useAppStore.getState();
const initialAuthState = useAuthStore.getState();

function renderSidebar() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe('Sidebar', () => {
  beforeEach(() => {
    useAppStore.setState({ ...initialAppState, sidebarCollapsed: false });
    useAuthStore.setState({
      ...initialAuthState,
      status: 'authenticated',
      accessToken: 'test-token',
      user: { id: 'user-1', email: 'hardik@example.com', createdAt: '2026-07-20T00:00:00Z' },
    });
  });

  afterEach(() => {
    useAppStore.setState(initialAppState);
    useAuthStore.setState(initialAuthState);
  });

  it('shows the authenticated email without a fabricated identity or plan', () => {
    renderSidebar();

    expect(screen.getByText('hardik@example.com')).toBeInTheDocument();
    expect(screen.getByText('H')).toBeInTheDocument();
    expect(screen.queryByText('Developer')).not.toBeInTheDocument();
    expect(screen.queryByText('Free Plan')).not.toBeInTheDocument();
  });

  it('derives primary navigation from the current navigable product surfaces', () => {
    renderSidebar();

    expect(
      screen.getAllByRole('link', {
        name: /Dashboard|Repositories|Upload Repository|Architecture|Dependency Graph|Settings|AI Workspace|Engineering Review|Documentation|Insights/,
      }),
    ).toHaveLength(10);
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Repositories' })).toHaveAttribute('href', '/repositories');
    expect(screen.getByRole('link', { name: 'Upload Repository' })).toHaveAttribute('href', '/upload');
    expect(screen.getByRole('link', { name: 'Architecture' })).toHaveAttribute('href', '/architecture');
    expect(screen.getByRole('link', { name: 'Dependency Graph' })).toHaveAttribute('href', '/dependencies');
    expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings');
    // Restored as Preview surfaces (#154): reachable from navigation, each
    // labelled Preview with its limitation on the page itself.
    expect(screen.getByRole('link', { name: 'AI Workspace' })).toHaveAttribute('href', '/ai-workspace');
    expect(screen.getByRole('link', { name: 'Documentation' })).toHaveAttribute('href', '/documentation');
    expect(screen.getByRole('link', { name: 'Engineering Review' })).toHaveAttribute('href', '/review');
    expect(screen.getByRole('link', { name: 'Insights' })).toHaveAttribute('href', '/insights');
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.queryByText('Experimental')).not.toBeInTheDocument();
    expect(screen.queryByText('Planned')).not.toBeInTheDocument();
  });

  it('keeps navigation links named and keyboard-focusable when collapsed', () => {
    renderSidebar();

    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }));

    const architecture = screen.getByRole('link', { name: 'Architecture' });
    architecture.focus();

    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument();
    expect(architecture).toHaveFocus();
    expect(architecture).toHaveAttribute('href', '/architecture');
  });

  it('marks only the active route with aria-current', () => {
    render(
      <MemoryRouter initialEntries={['/architecture']}>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Architecture' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Repositories' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Settings' })).not.toHaveAttribute('aria-current');
  });
});
