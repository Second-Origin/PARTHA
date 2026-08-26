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
