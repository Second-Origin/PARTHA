import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { aiService, getErrorMessage } from '@/shared/services/api';
import type { AiProvider, AiProviderCapability, AiProviderPublicConfig } from '@/shared/services/api/types';

export const settingsTabs = ['General', 'AI Providers', 'Notifications', 'API Keys'] as const;
export type SettingsTab = (typeof settingsTabs)[number];

const TAB_QUERY_PARAM = 'tab';

function isSettingsTab(value: string | null): value is SettingsTab {
  return settingsTabs.includes(value as SettingsTab);
}

export function useSettings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get(TAB_QUERY_PARAM);
  const [activeTab, setActiveTabState] = useState<SettingsTab>(
    isSettingsTab(tabFromUrl) ? tabFromUrl : 'General',
  );

  useEffect(() => {
    if (isSettingsTab(tabFromUrl) && tabFromUrl !== activeTab) {
      setActiveTabState(tabFromUrl);
    }
    // Only react to the URL changing out from under us (e.g. a link into
    // Settings); setActiveTab below is the source of truth for user clicks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabFromUrl]);

  const setActiveTab = useCallback(
    (tab: SettingsTab) => {
      setActiveTabState(tab);
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous);
        next.set(TAB_QUERY_PARAM, tab);
        return next;
      });
    },
    [setSearchParams],
  );

  const [capabilities, setCapabilities] = useState<AiProviderCapability[]>([]);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);
  const capabilityByProvider = useMemo(
    () => new Map(capabilities.map((capability) => [capability.provider, capability])),
    [capabilities],
  );

  const [aiConfig, setAiConfig] = useState<AiProviderPublicConfig | null>(null);
  const [provider, setProvider] = useState<AiProvider>('openai');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [providersResponse, config] = await Promise.all([aiService.getProviders(), aiService.getConfig()]);
        if (cancelled) return;
        setCapabilities(providersResponse.providers);
        setAiConfig(config);
        const defaultModelFor = (id: AiProvider) =>
          providersResponse.providers.find((capability) => capability.provider === id)?.defaultModel ?? '';
        if (config.provider) {
          setProvider(config.provider);
          setModel(config.model || defaultModelFor(config.provider));
          setBaseUrl(config.baseUrl || '');
        } else {
          setModel(defaultModelFor('openai'));
        }
      } catch (caught) {
        if (!cancelled) setCapabilitiesError(getErrorMessage(caught));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const chooseProvider = useCallback(
    (nextProvider: AiProvider) => {
      setProvider(nextProvider);
      setModel(capabilityByProvider.get(nextProvider)?.defaultModel ?? '');
      setStatusMessage(null);
      setError(null);
    },
    [capabilityByProvider],
  );

  const saveAiConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const defaultModel = capabilityByProvider.get(provider)?.defaultModel;
      const config = await aiService.saveConfig({
        provider,
        apiKey: apiKey.trim() || undefined,
        model: model.trim() || defaultModel,
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
  }, [apiKey, baseUrl, capabilityByProvider, model, provider]);

  const testAiConfig = useCallback(async () => {
    setTesting(true);
    setError(null);
    setStatusMessage(null);
    try {
      const defaultModel = capabilityByProvider.get(provider)?.defaultModel;
      const response = await aiService.testConfig({
        provider,
        apiKey: apiKey.trim() || undefined,
        model: model.trim() || defaultModel,
        baseUrl: baseUrl.trim() || undefined,
      });
      setStatusMessage(response.message);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setTesting(false);
    }
  }, [apiKey, baseUrl, capabilityByProvider, model, provider]);

  return {
    tabs: settingsTabs,
    activeTab,
    setActiveTab,
    capabilities,
    capabilitiesError,
    activeCapability: capabilityByProvider.get(provider) ?? null,
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
