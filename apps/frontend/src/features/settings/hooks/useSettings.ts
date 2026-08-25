import { useCallback, useEffect, useState } from 'react';
import { aiService, getErrorMessage } from '@/shared/services/api';
import type { AiProvider, AiProviderPublicConfig } from '@/shared/services/api/types';

export const settingsTabs = ['General', 'AI Providers', 'Notifications', 'API Keys'] as const;
export type SettingsTab = (typeof settingsTabs)[number];

const defaultModels: Record<AiProvider, string> = {
  openai: 'gpt-4o-mini',
  anthropic: 'claude-3-5-haiku-latest',
  gemini: 'gemini-1.5-flash',
  openrouter: 'openai/gpt-4o-mini',
  ollama: 'llama3.2',
};

export function useSettings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('General');
  const [aiConfig, setAiConfig] = useState<AiProviderPublicConfig | null>(null);
  const [provider, setProvider] = useState<AiProvider>('openai');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState(defaultModels.openai);
  const [baseUrl, setBaseUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const config = await aiService.getConfig();
        if (cancelled) return;
        setAiConfig(config);
        if (config.provider) {
          setProvider(config.provider);
          setModel(config.model || defaultModels[config.provider]);
          setBaseUrl(config.baseUrl || '');
        }
      } catch (caught) {
        if (!cancelled) setError(getErrorMessage(caught));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const chooseProvider = useCallback((nextProvider: AiProvider) => {
    setProvider(nextProvider);
    setModel(defaultModels[nextProvider]);
    setStatusMessage(null);
    setError(null);
  }, []);

  const saveAiConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const config = await aiService.saveConfig({
        provider,
        apiKey: apiKey.trim() || undefined,
        model: model.trim() || defaultModels[provider],
        baseUrl: baseUrl.trim() || undefined,
      });
      setAiConfig(config);
      setApiKey('');
      setStatusMessage('AI provider saved.');
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [apiKey, baseUrl, model, provider]);

  const testAiConfig = useCallback(async () => {
    setTesting(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await aiService.testConfig({
        provider,
        apiKey: apiKey.trim() || undefined,
        model: model.trim() || defaultModels[provider],
        baseUrl: baseUrl.trim() || undefined,
      });
      setStatusMessage(response.message);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setTesting(false);
    }
  }, [apiKey, baseUrl, model, provider]);

  return {
    tabs: settingsTabs,
    activeTab,
    setActiveTab,
    aiConfig,
    provider,
    setProvider: chooseProvider,
    apiKey,
    setApiKey,
    model,
    setModel,
    baseUrl,
    setBaseUrl,
    saveAiConfig,
    testAiConfig,
    testing,
    statusMessage,
    loading,
    error,
    empty: false,
    success: true,
    retry: () => undefined,
    refresh: () => undefined,
  };
}
