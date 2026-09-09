import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { useAuthStore } from '@/app/store/useAuthStore';
import { primaryNavigationSurfaces } from '@/app/routes/productSurfaces';
import { Sidebar } from './Sidebar';

/** Sidebar reads isMobile from a real matchMedia('(max-width: 767px)') query
 * in a mount-time effect; the global test-setup stub always reports
 * `matches: false`, so mobile-drawer tests need their own stub reporting
 * true for that specific query. */
function stubMobileViewport() {
  const original = window.matchMedia;
  window.matchMedia = ((query: string) => ({
    matches: query === '(max-width: 767px)',
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
  return () => {
    window.matchMedia = original;
  };
}

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
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard');
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

  it('groups the flagship surfaces first, unlabelled, exactly as Dashboard/Repositories/Upload (#289)', () => {
    renderSidebar();

    const flagship = primaryNavigationSurfaces.filter((item) => item.navGroup === 'flagship');
    expect(flagship.map((item) => item.label)).toEqual(['Dashboard', 'Repositories', 'Upload Repository']);
    for (const item of flagship) {
      const link = screen.getByRole('link', { name: item.label });
      expect(link.className).toContain('font-medium');
    }
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

  it('groups Architecture/Dependencies/Engineering Review/Insights/Documentation under a labelled "Analysis" section, in that order (#289)', () => {
    renderSidebar();

    const analysis = primaryNavigationSurfaces.filter((item) => item.navGroup === 'analysis');
    expect(analysis.map((item) => item.label)).toEqual([
      'Architecture',
      'Dependency Graph',
      'Engineering Review',
      'Insights',
      'Documentation',
    ]);

    const analysisLabel = screen.getByText('Analysis');
    expect(analysisLabel).toBeInTheDocument();

    // Every analysis surface is still a real, reachable, focusable link --
    // grouping under a label never means "hide" or "remove".
    for (const item of analysis) {
      const link = screen.getByRole('link', { name: item.label });
      expect(link).toHaveAttribute('href', item.path);
      expect(link.className).toContain('font-normal');
    }

    // The "Analysis" heading sits after every flagship link and before every
    // analysis-group link.
    const dashboardLink = screen.getByRole('link', { name: 'Dashboard' });
    const firstAnalysisLink = screen.getByRole('link', { name: analysis[0].label });
    expect(dashboardLink.compareDocumentPosition(analysisLabel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(analysisLabel.compareDocumentPosition(firstAnalysisLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(dashboardLink.className).toContain('font-medium');
  });

  it('keeps AI Workspace reachable under its own "Assist" section, separate from Analysis (#289)', () => {
    renderSidebar();

    const assist = primaryNavigationSurfaces.filter((item) => item.navGroup === 'assist');
    expect(assist.map((item) => item.label)).toEqual(['AI Workspace']);

    const assistLabel = screen.getByText('Assist');
    const analysisLabel = screen.getByText('Analysis');
    const aiWorkspaceLink = screen.getByRole('link', { name: 'AI Workspace' });
    expect(aiWorkspaceLink).toHaveAttribute('href', '/ai-workspace');
    expect(analysisLabel.compareDocumentPosition(assistLabel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('pins Settings to the bottom, separated from the scrollable nav and above the account identity (#289)', () => {
    renderSidebar();

    const settingsLink = screen.getByRole('link', { name: 'Settings' });
    const assistLabel = screen.getByText('Assist');
    const accountEmail = screen.getByText('hardik@example.com');

    // Settings renders after every scrollable-nav item and before the
    // account-identity row, and sits in its own visually separated block.
    expect(assistLabel.compareDocumentPosition(settingsLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(settingsLink.compareDocumentPosition(accountEmail) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // Pinned out of the scrollable primary list, but still inside a landmark:
    // a link in a bare <div> is invisible to landmark-based navigation.
    const settingsNav = settingsLink.closest('nav');
    expect(settingsNav).not.toBeNull();
    expect(settingsNav).toHaveAttribute('aria-label', 'Settings');
    expect(settingsNav).not.toBe(screen.getByRole('navigation', { name: 'Primary navigation' }));
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

describe('Sidebar mobile drawer (#317)', () => {
  let restoreMatchMedia: () => void;

  beforeEach(() => {
    restoreMatchMedia = stubMobileViewport();
    useAuthStore.setState({
      ...initialAuthState,
      status: 'authenticated',
      accessToken: 'test-token',
      user: { id: 'user-1', email: 'hardik@example.com', createdAt: '2026-07-20T00:00:00Z' },
    });
  });

  afterEach(() => {
    restoreMatchMedia();
    useAppStore.setState(initialAppState);
    useAuthStore.setState(initialAuthState);
  });

  it('is a labelled, non-modal, inert drawer while closed on a mobile viewport', () => {
    useAppStore.setState({ ...initialAppState, mobileSidebarOpen: false });

    renderSidebar();

    const drawer = screen.getByRole('dialog', { hidden: true });
    expect(drawer).toHaveAttribute('aria-label', 'Navigation drawer');
    expect(drawer).not.toHaveAttribute('aria-modal', 'true');
    expect(drawer).toHaveProperty('inert', true);
  });

  it('opens as a labelled modal dialog and moves focus to its close control', () => {
    useAppStore.setState({ ...initialAppState, mobileSidebarOpen: true });

    renderSidebar();

    const drawer = screen.getByRole('dialog');
    expect(drawer).toHaveAttribute('aria-label', 'Navigation drawer');
    expect(drawer).toHaveAttribute('aria-modal', 'true');
    expect(drawer).toHaveProperty('inert', false);
    // Scoped to the drawer itself: the backdrop button outside it shares the
    // same accessible name ("Close navigation drawer") by design.
    expect(within(drawer).getByRole('button', { name: 'Close navigation drawer' })).toHaveFocus();
  });

  it('closes on Escape', () => {
    useAppStore.setState({ ...initialAppState, mobileSidebarOpen: true });
    renderSidebar();

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(useAppStore.getState().mobileSidebarOpen).toBe(false);
  });

  it('closes when the backdrop is activated', () => {
    useAppStore.setState({ ...initialAppState, mobileSidebarOpen: true });
    renderSidebar();

    // The backdrop button and the drawer's own close button share the exact
    // same accessible name ("Close navigation drawer") by design -- both
    // close the drawer, so both should announce that. Scope to outside the
    // dialog to get the backdrop specifically.
    const drawer = screen.getByRole('dialog');
    const backdrop = screen
      .getAllByRole('button', { name: 'Close navigation drawer' })
      .find((button) => !drawer.contains(button));
    fireEvent.click(backdrop!);

    expect(useAppStore.getState().mobileSidebarOpen).toBe(false);
  });

  it('closes after activating a navigation link, the same way the close button does', () => {
    useAppStore.setState({ ...initialAppState, mobileSidebarOpen: true });
    renderSidebar();

    fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }));

    expect(useAppStore.getState().mobileSidebarOpen).toBe(false);
  });

  it('returns focus to the control that opened it once the drawer closes', () => {
    useAppStore.setState({ ...initialAppState, mobileSidebarOpen: false });
    renderSidebar();

    const opener = document.createElement('button');
    opener.textContent = 'Open navigation drawer';
    document.body.appendChild(opener);
    opener.focus();
    expect(opener).toHaveFocus();

    act(() => {
      useAppStore.setState({ mobileSidebarOpen: true });
    });
    // Same shared accessible name as the backdrop-close test above; scope to
    // the dialog to get the drawer's own close button specifically.
    const drawer = screen.getByRole('dialog');
    expect(within(drawer).getByRole('button', { name: 'Close navigation drawer' })).toHaveFocus();

    act(() => {
      useAppStore.setState({ mobileSidebarOpen: false });
    });
    expect(opener).toHaveFocus();

    opener.remove();
  });
});
