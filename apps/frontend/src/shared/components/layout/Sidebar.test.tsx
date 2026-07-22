import { render, screen } from '@testing-library/react';
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

  it('keeps core navigation available and hides deferred surfaces from primary navigation', () => {
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Architecture' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dependency Graph' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Engineering Review' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'AI Workspace' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Documentation' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Insights' })).not.toBeInTheDocument();
  });
});
