import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, afterEach, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { MainLayout } from './MainLayout';

const initialAppState = useAppStore.getState();

vi.mock('./Sidebar', () => ({ Sidebar: () => <nav data-testid="sidebar-stub" /> }));
vi.mock('./TopBar', () => ({ TopBar: () => <header data-testid="topbar-stub" /> }));
vi.mock('@/features/repositories/context/RepositoryProvider', () => ({
  RepositoryProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

function renderMainLayout() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<div data-testid="page-content">Page content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('MainLayout', () => {
  afterEach(() => {
    useAppStore.setState(initialAppState);
  });

  it('renders the sidebar, top bar, and the routed page content together', () => {
    renderMainLayout();

    expect(screen.getByTestId('sidebar-stub')).toBeInTheDocument();
    expect(screen.getByTestId('topbar-stub')).toBeInTheDocument();
    expect(screen.getByTestId('page-content')).toBeInTheDocument();
  });

  it('reserves the expanded sidebar width when the sidebar is not collapsed', () => {
    useAppStore.setState({ sidebarCollapsed: false });

    renderMainLayout();

    expect(screen.getByTestId('page-content').closest('div.flex.min-w-0.flex-1')).toHaveClass('md:ml-[248px]');
  });

  it('reserves the collapsed sidebar width when the sidebar is collapsed', () => {
    useAppStore.setState({ sidebarCollapsed: true });

    renderMainLayout();

    expect(screen.getByTestId('page-content').closest('div.flex.min-w-0.flex-1')).toHaveClass('md:ml-16');
  });
});
