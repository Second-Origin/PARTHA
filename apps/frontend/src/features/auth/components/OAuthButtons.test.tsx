import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OAuthButtons } from './OAuthButtons';
import { authService, getErrorMessage } from '@/shared/services/api';

vi.mock('@/shared/services/api', () => ({
  authService: { getOAuthProviders: vi.fn(), startOAuthLogin: vi.fn() },
  getErrorMessage: vi.fn((error: unknown) => String(error)),
}));

beforeEach(() => {
  vi.mocked(authService.getOAuthProviders).mockReset();
  vi.mocked(authService.startOAuthLogin).mockReset();
  vi.mocked(getErrorMessage).mockImplementation((error: unknown) => String(error));
});

describe('OAuthButtons', () => {
  it('renders nothing while the capability check is in flight or once it resolves empty', async () => {
    vi.mocked(authService.getOAuthProviders).mockResolvedValue({ providers: [] });

    const { container } = render(<OAuthButtons />);

    expect(container).toBeEmptyDOMElement();
    await waitFor(() => expect(authService.getOAuthProviders).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders a button only for each configured provider', async () => {
    vi.mocked(authService.getOAuthProviders).mockResolvedValue({ providers: ['google'] });

    render(<OAuthButtons />);

    expect(await screen.findByTestId('oauth-button-google')).toBeInTheDocument();
    expect(screen.queryByTestId('oauth-button-github')).not.toBeInTheDocument();
  });

  it('navigates the browser to the returned authorize URL on click', async () => {
    vi.mocked(authService.getOAuthProviders).mockResolvedValue({ providers: ['github'] });
    vi.mocked(authService.startOAuthLogin).mockResolvedValue({ authorizeUrl: 'https://github.example/authorize' });
    const assignSpy = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign: assignSpy });

    render(<OAuthButtons />);
    const button = await screen.findByTestId('oauth-button-github');
    fireEvent.click(button);

    await waitFor(() => expect(assignSpy).toHaveBeenCalledWith('https://github.example/authorize'));
    expect(authService.startOAuthLogin).toHaveBeenCalledWith('github');

    vi.unstubAllGlobals();
  });

  it('shows an error and re-enables the button if starting the flow fails', async () => {
    vi.mocked(authService.getOAuthProviders).mockResolvedValue({ providers: ['google'] });
    vi.mocked(authService.startOAuthLogin).mockRejectedValue(new Error('provider unavailable'));

    render(<OAuthButtons />);
    const button = await screen.findByTestId('oauth-button-google');
    fireEvent.click(button);

    expect(await screen.findByRole('alert')).toHaveTextContent('provider unavailable');
    expect(button).not.toBeDisabled();
  });
});
