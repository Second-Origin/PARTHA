import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';

vi.mock('@/features/settings/hooks/useSettings', () => ({
  useSettings: () => ({
    tabs: ['General', 'AI Providers', 'Appearance', 'Notifications', 'API Keys'],
    activeTab: 'Notifications',
    setActiveTab: vi.fn(),
  }),
}));

describe('SettingsPage notification preferences', () => {
  it('discloses the upcoming state and gives each disabled switch a unique accessible name', () => {
    render(<SettingsPage />);

    expect(screen.getByText('Coming Soon')).toBeVisible();
    expect(
      screen.getByText('Notification preferences are in development and cannot be configured yet.'),
    ).toBeVisible();

    for (const preference of ['Analysis complete', 'Error alerts', 'New insights available']) {
      const control = screen.getByRole('switch', {
        name: `${preference} notifications (coming soon)`,
      });

      expect(control).toBeDisabled();
      expect(control).toHaveAttribute('aria-checked', 'false');
      expect(within(control).getByRole('generic', { hidden: true })).toHaveAttribute('aria-hidden', 'true');
    }
  });
});
