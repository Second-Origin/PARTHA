import { act, renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSettings } from './useSettings';
import { aiService } from '@/shared/services/api';
import type { AiProviderCapabilitiesResponse, AiProviderPublicConfig } from '@/shared/services/api/types';

vi.mock('@/shared/services/api', () => ({
  aiService: {
    getProviders: vi.fn(),
    getConfig: vi.fn(),
    saveConfig: vi.fn(),
    testConfig: vi.fn(),
  },
  getErrorMessage: vi.fn((error: unknown) => String(error)),
}));

const CAPABILITIES: AiProviderCapabilitiesResponse = {
  providers: [
    {
      provider: 'openai',
      displayName: 'OpenAI',
      requiresApiKey: true,
      requiresBaseUrl: false,
      defaultModel: 'gpt-4o-mini',
      setupUrl: 'https://platform.openai.com/api-keys',
      setupSteps: ['Create an OpenAI account and generate an API key.', 'Test the connection, then save.'],
      supportState: 'supported',
    },
    {
      provider: 'ollama',
      displayName: 'Ollama',
      requiresApiKey: false,
      requiresBaseUrl: true,
      defaultModel: 'llama3.2',
      setupUrl: 'https://ollama.com/download',
      setupSteps: ["Install and start Ollama, either locally or on a server you control.", "Enter the base URL where it's running."],
      supportState: 'supported',
    },
  ],
};

const EMPTY_CONFIG: AiProviderPublicConfig = {
  provider: null,
  model: null,
  baseUrl: null,
  hasApiKey: false,
  apiKeyLast4: null,
};

function wrapper(initialEntry = '/settings') {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      MemoryRouter,
      { initialEntries: [initialEntry] },
      createElement(Routes, null, createElement(Route, { path: '/settings', element: children })),
    );
  };
}

beforeEach(() => {
  vi.mocked(aiService.getProviders).mockResolvedValue(CAPABILITIES);
  vi.mocked(aiService.getConfig).mockResolvedValue(EMPTY_CONFIG);
});

describe('useSettings capability loading', () => {
  it('fetches provider capabilities and config together, defaulting to openai', async () => {
    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.capabilities).toHaveLength(2));

    expect(result.current.provider).toBe('openai');
    expect(result.current.model).toBe('gpt-4o-mini');
    expect(result.current.activeCapability?.displayName).toBe('OpenAI');
    expect(result.current.capabilitiesError).toBeNull();
  });

  it('picks up a previously saved provider and its model, not the openai default', async () => {
    vi.mocked(aiService.getConfig).mockResolvedValue({
      provider: 'ollama',
      model: 'llama3.2',
      baseUrl: 'http://localhost:11434',
      hasApiKey: false,
      apiKeyLast4: null,
    });

    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.provider).toBe('ollama'));
    expect(result.current.model).toBe('llama3.2');
    expect(result.current.baseUrl).toBe('http://localhost:11434');
    expect(result.current.activeCapability?.requiresApiKey).toBe(false);
    expect(result.current.activeCapability?.requiresBaseUrl).toBe(true);
  });

  it('surfaces a capability-fetch failure as capabilitiesError', async () => {
    vi.mocked(aiService.getProviders).mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });

    await waitFor(() => expect(result.current.capabilitiesError).toBe('Error: network down'));
    expect(result.current.capabilities).toHaveLength(0);
  });

  it('switching provider resets the model to that provider capability default', async () => {
    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.capabilities).toHaveLength(2));

    act(() => result.current.setProvider('ollama'));

    expect(result.current.provider).toBe('ollama');
    expect(result.current.model).toBe('llama3.2');
    expect(result.current.activeCapability?.requiresApiKey).toBe(false);
  });
});

describe('useSettings tab deep-linking', () => {
  it('reads the initial tab from the ?tab= query parameter', async () => {
    const { result } = renderHook(() => useSettings(), { wrapper: wrapper('/settings?tab=AI+Providers') });

    expect(result.current.activeTab).toBe('AI Providers');
  });

  it('ignores an unrecognised ?tab= value and falls back to General', async () => {
    const { result } = renderHook(() => useSettings(), { wrapper: wrapper('/settings?tab=Nonsense') });

    expect(result.current.activeTab).toBe('General');
  });

  it('setActiveTab updates state so the page can re-render the newly selected tab', async () => {
    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });

    act(() => result.current.setActiveTab('Notifications'));

    expect(result.current.activeTab).toBe('Notifications');
  });
});

describe('useSettings base URL handling across providers', () => {
  const OLLAMA_SAVED: AiProviderPublicConfig = {
    provider: 'ollama',
    model: 'llama3.2',
    baseUrl: 'http://localhost:11434',
    hasApiKey: false,
    apiKeyLast4: null,
  };

  it('does not carry a saved Ollama base URL into a fixed-endpoint provider', async () => {
    // The reported sequence: Ollama is saved, the user switches to a hosted
    // provider, and the backend answers "AI provider destination is not
    // permitted." because a fixed destination rejects any base URL -- while
    // the form shows no base URL field to clear, so the value is invisible.
    vi.mocked(aiService.getConfig).mockResolvedValue(OLLAMA_SAVED);
    vi.mocked(aiService.testConfig).mockResolvedValue({ ok: true, message: 'Connected.' });
    vi.mocked(aiService.saveConfig).mockResolvedValue(EMPTY_CONFIG);

    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.baseUrl).toBe('http://localhost:11434'));

    act(() => result.current.setProvider('openai'));
    expect(result.current.baseUrl).toBe('');

    await act(async () => {
      await result.current.testAiConfig();
    });
    expect(vi.mocked(aiService.testConfig).mock.lastCall?.[0].baseUrl).toBeUndefined();

    await act(async () => {
      await result.current.saveAiConfig();
    });
    expect(vi.mocked(aiService.saveConfig).mock.lastCall?.[0].baseUrl).toBeUndefined();
  });

  it('still sends the base URL for a provider that requires one', async () => {
    vi.mocked(aiService.getConfig).mockResolvedValue(OLLAMA_SAVED);
    vi.mocked(aiService.saveConfig).mockResolvedValue(OLLAMA_SAVED);

    const { result } = renderHook(() => useSettings(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.baseUrl).toBe('http://localhost:11434'));

    await act(async () => {
      await result.current.saveAiConfig();
    });
    expect(vi.mocked(aiService.saveConfig).mock.lastCall?.[0].baseUrl).toBe('http://localhost:11434');
  });
});
