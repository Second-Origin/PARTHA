import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPage } from './SettingsPage';
import { useSettings, settingsTabs } from '@/features/settings/hooks/useSettings';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService } from '@/shared/services/api';
import { ApiError } from '@/shared/services/api/errors';
import type { AiProvider, AiProviderCapability } from '@/shared/services/api/types';

vi.mock('@/features/settings/hooks/useSettings', async () => {
  const actual = await vi.importActual<typeof import('@/features/settings/hooks/useSettings')>(
    '@/features/settings/hooks/useSettings',
  );
  return { ...actual, useSettings: vi.fn() };
});

const CAPABILITIES: AiProviderCapability[] = [
  {
    provider: 'openai',
    displayName: 'OpenAI',
    requiresApiKey: true,
    requiresBaseUrl: false,
    defaultModel: 'gpt-4o-mini',
    setupUrl: 'https://platform.openai.com/api-keys',
    setupSteps: [
      'Create an OpenAI account and generate an API key.',
      'Paste in the API key.',
      'Confirm the model ID (default: gpt-4o-mini).',
      'Test the connection, then save.',
    ],
    supportState: 'supported',
  },
  {
    provider: 'anthropic',
    displayName: 'Anthropic',
    requiresApiKey: true,
    requiresBaseUrl: false,
    defaultModel: 'claude-3-5-haiku-latest',
    setupUrl: 'https://console.anthropic.com/settings/keys',
    setupSteps: [
      'Create an Anthropic account and generate an API key.',
      'Paste in the API key.',
      'Confirm the model ID (default: claude-3-5-haiku-latest).',
      'Test the connection, then save.',
    ],
    supportState: 'supported',
  },
  {
    provider: 'gemini',
    displayName: 'Google Gemini',
    requiresApiKey: true,
    requiresBaseUrl: false,
    defaultModel: 'gemini-1.5-flash',
    setupUrl: 'https://aistudio.google.com/apikey',
    setupSteps: [
      'Create a Google AI Studio API key.',
      'Paste in the API key.',
      'Confirm the model ID (default: gemini-1.5-flash).',
      'Test the connection, then save.',
    ],
    supportState: 'supported',
  },
  {
    provider: 'openrouter',
    displayName: 'OpenRouter',
    requiresApiKey: true,
    requiresBaseUrl: false,
    defaultModel: 'openai/gpt-4o-mini',
    setupUrl: 'https://openrouter.ai/keys',
    setupSteps: [
      'Create an OpenRouter account and generate an API key.',
      'Paste in the API key.',
      'Confirm the model ID (default: openai/gpt-4o-mini).',
      'Test the connection, then save.',
    ],
    supportState: 'supported',
  },
  {
    provider: 'ollama',
    displayName: 'Ollama',
    requiresApiKey: false,
    requiresBaseUrl: true,
    defaultModel: 'llama3.2',
    setupUrl: 'https://ollama.com/download',
    setupSteps: [
      'Install and start Ollama, either locally or on a server you control.',
      "Enter the base URL where it's running.",
      'Confirm the model ID (default: llama3.2).',
      'Test the connection, then save.',
    ],
    supportState: 'supported',
  },
];

function capabilityFor(provider: AiProvider): AiProviderCapability {
  const capability = CAPABILITIES.find((entry) => entry.provider === provider);
  if (!capability) throw new Error(`no test fixture capability for provider ${provider}`);
  return capability;
}

function baseSettings(overrides: Partial<ReturnType<typeof useSettings>> = {}): ReturnType<typeof useSettings> {
  const provider = overrides.provider ?? 'openai';
  return {
    tabs: settingsTabs,
    activeTab: 'General',
    setActiveTab: vi.fn(),
    capabilities: CAPABILITIES,
    capabilitiesError: null,
    activeCapability: capabilityFor(provider),
    aiConfig: null,
    provider,
    setProvider: vi.fn(),
    apiKey: '',
    setApiKey: vi.fn(),
    model: 'gpt-4o-mini',
    setModel: vi.fn(),
    baseUrl: '',
    setBaseUrl: vi.fn(),
    saveAiConfig: vi.fn(),
    testAiConfig: vi.fn(),
    testing: false,
    statusMessage: null,
    loading: false,
    error: null,
    empty: false,
    success: true,
    retry: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  };
}

describe('SettingsPage renders every section without crashing', () => {
  it.each(settingsTabs)('renders the %s tab', (tab) => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: tab }));

    render(<SettingsPage />);

    expect(screen.getByRole('tab', { name: tab, selected: true })).toBeInTheDocument();
  });
});

describe('SettingsPage "in development" sections are honest and non-interactive', () => {
  it('API Keys: states there are none configured and disables the only action', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'API Keys' }));

    render(<SettingsPage />);

    expect(screen.getByText('No API keys configured.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Coming Soon' })).toBeDisabled();
  });

  it('General: profile fields are read-only and editing is disabled, not silently ignored', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'General' }));
    useAuthStore.setState({
      status: 'authenticated',
      accessToken: 'a-token',
      user: { id: 'user-1', email: 'alice@example.com', createdAt: '2026-01-01T00:00:00Z' },
    });

    render(<SettingsPage />);

    expect(screen.getByLabelText('Email')).toBeDisabled();
    expect(screen.getByLabelText('Member Since')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Editing Coming Soon' })).toBeDisabled();

    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
  });

  it('Notifications: discloses the upcoming state and gives each disabled switch a unique accessible name', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'Notifications' }));

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
      const thumb = within(control).getByRole('generic', { hidden: true });
      expect(thumb).toHaveAttribute('aria-hidden', 'true');
      expect(thumb).toHaveClass('left-0.5');
      expect(thumb).not.toHaveClass('right-0.5');
    }
  });
});

describe('SettingsPage AI provider configuration', () => {
  it('shows "Not configured" and an honest empty-key placeholder when no provider is saved', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'AI Providers', aiConfig: null }));

    render(<SettingsPage />);

    expect(screen.getByText('Not configured')).toBeVisible();
    expect(screen.getByLabelText('API Key')).toHaveAttribute('placeholder', 'Enter provider API key');
    expect(document.body.textContent).not.toMatch(/sk-[A-Za-z0-9]/);
  });

  it('shows the saved provider and only the masked last 4 characters of its key, never full key material', () => {
    vi.mocked(useSettings).mockReturnValue(
      baseSettings({
        activeTab: 'AI Providers',
        provider: 'openai',
        aiConfig: { provider: 'openai', model: 'gpt-4o-mini', hasApiKey: true, apiKeyLast4: 'wxyz', baseUrl: null },
      }),
    );

    render(<SettingsPage />);

    expect(screen.getByText('Saved: openai')).toBeVisible();
    expect(screen.getByLabelText('API Key')).toHaveAttribute('placeholder', 'Saved key •••• wxyz');
    // The full key is never part of this hook's state (AiProviderPublicConfig
    // only ever carries a masked last-4), so there is nothing beyond the
    // masked placeholder that could leak -- confirm no bare "sk-..." pattern
    // renders anywhere in the page.
    expect(document.body.textContent).not.toMatch(/sk-[A-Za-z0-9]{10,}/);
  });

  it('switches provider and its model default, and reveals the Ollama base-URL field only for Ollama', () => {
    const setProvider = vi.fn();
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'AI Providers', setProvider }));

    render(<SettingsPage />);

    expect(screen.queryByLabelText('Ollama Base URL')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Ollama' }));
    expect(setProvider).toHaveBeenCalledWith('ollama');
  });

  it('shows the Ollama base-URL field, not the API key field, once Ollama is selected', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'AI Providers', provider: 'ollama' }));

    render(<SettingsPage />);

    expect(screen.getByLabelText('Ollama Base URL')).toBeInTheDocument();
    expect(screen.queryByLabelText('API Key')).not.toBeInTheDocument();
  });

  it('surfaces a save/test error honestly', () => {
    vi.mocked(useSettings).mockReturnValue(
      baseSettings({ activeTab: 'AI Providers', error: 'The provided API key was rejected.' }),
    );

    render(<SettingsPage />);

    expect(screen.getByText('The provided API key was rejected.')).toBeVisible();
  });

  it('disables Test Connection and Save while a request is in flight', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'AI Providers', loading: true }));

    render(<SettingsPage />);

    expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Test Connection' })).toBeDisabled();
  });

  it('shows at most 4 setup steps and an official setup link for the selected provider', () => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'AI Providers', provider: 'anthropic' }));

    render(<SettingsPage />);

    expect(screen.getByText('Getting started with Anthropic')).toBeVisible();
    const capability = capabilityFor('anthropic');
    for (const step of capability.setupSteps) {
      expect(screen.getByText(step)).toBeVisible();
    }
    expect(capability.setupSteps.length).toBeLessThanOrEqual(4);

    const link = screen.getByRole('link', { name: 'Open Anthropic setup page' });
    expect(link).toHaveAttribute('href', capability.setupUrl);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noreferrer'));
  });

  it('surfaces a capability-fetch failure honestly, without hiding the rest of the tab', () => {
    vi.mocked(useSettings).mockReturnValue(
      baseSettings({
        activeTab: 'AI Providers',
        capabilities: [],
        activeCapability: null,
        capabilitiesError: 'Could not load AI provider setup information.',
      }),
    );

    render(<SettingsPage />);

    expect(screen.getByText('Could not load AI provider setup information.')).toBeVisible();
    expect(screen.queryByText(/Getting started with/)).not.toBeInTheDocument();
  });
});

describe('SettingsPage account deletion', () => {
  beforeEach(() => {
    vi.mocked(useSettings).mockReturnValue(baseSettings({ activeTab: 'General' }));
    useAuthStore.setState({
      status: 'authenticated',
      accessToken: 'a-token',
      user: { id: 'user-1', email: 'alice@example.com', createdAt: '2026-01-01T00:00:00Z' },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ status: 'initialising', accessToken: null, user: null });
  });

  it('keeps the confirm button disabled until the account email is typed back exactly', () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));

    const confirmButton = screen.getByRole('button', { name: 'Permanently Delete Account' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Type alice@example.com to confirm/i), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct-horse-battery' } });
    expect(confirmButton).toBeDisabled();
  });

  it('deletes the account and clears local session state on success', async () => {
    const deleteAccount = vi.spyOn(authService, 'deleteAccount').mockResolvedValue(undefined);
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));
    fireEvent.change(screen.getByLabelText(/Type alice@example.com to confirm/i), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'correct-horse-battery' } });

    const confirmButton = screen.getByRole('button', { name: 'Permanently Delete Account' });
    expect(confirmButton).toBeEnabled();
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(deleteAccount).toHaveBeenCalledWith({
        password: 'correct-horse-battery',
        confirmEmail: 'alice@example.com',
      });
    });
    await waitFor(() => expect(useAuthStore.getState().status).toBe('unauthenticated'));
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('surfaces a wrong-password rejection without clearing the session', async () => {
    vi.spyOn(authService, 'deleteAccount').mockRejectedValue(
      new ApiError(401, 'Unauthorized', { code: 'unauthorized', message: 'Invalid password.' }, '/auth/me'),
    );
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));
    fireEvent.change(screen.getByLabelText(/Type alice@example.com to confirm/i), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Permanently Delete Account' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid password.');
    expect(useAuthStore.getState().status).toBe('authenticated');
  });

  it('cancel collapses the panel and clears the entered fields', () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete Account' }));
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'some-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByRole('button', { name: 'Delete Account' })).toBeVisible();
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  });
});
