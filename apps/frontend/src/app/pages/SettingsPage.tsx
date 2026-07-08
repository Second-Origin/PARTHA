import { PageHeader } from '@/shared/components/ui/PageHeader';
import { useSettings } from '@/features/settings/hooks/useSettings';
import { cn } from '@/shared/utils/cn';

export function SettingsPage() {
  const settings = useSettings();
  const { tabs, activeTab, setActiveTab } = settings;
  const providers = [
    ['openai', 'OpenAI'],
    ['anthropic', 'Anthropic'],
    ['gemini', 'Google Gemini'],
    ['openrouter', 'OpenRouter'],
    ['ollama', 'Ollama'],
  ] as const;

  return (
    <div className="max-w-3xl">
      <PageHeader title="Settings" description="Manage your account and preferences" />

      <div className="flex items-center gap-1 border-b border-border mb-6">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium transition-colors relative',
              activeTab === tab ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {tab}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
            )}
          </button>
        ))}
      </div>

      <div className="space-y-6">
        {activeTab === 'General' && (
          <div className="space-y-6">
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="text-sm font-medium text-foreground mb-4">Profile</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Display Name</label>
                  <input
                    type="text"
                    defaultValue="Developer"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Email</label>
                  <input
                    type="email"
                    placeholder="you@example.com"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button disabled className="rounded-md bg-muted px-4 py-2 text-sm font-medium text-muted-foreground cursor-not-allowed">
                  Coming Soon
                </button>
              </div>
            </div>
            <div className="rounded-xl border border-destructive/50 bg-card p-6">
              <h3 className="text-sm font-medium text-destructive mb-2">Danger Zone</h3>
              <p className="text-xs text-muted-foreground mb-4">Permanently delete your account and all data.</p>
              <button disabled className="rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground cursor-not-allowed">
                Coming Soon
              </button>
            </div>
          </div>
        )}
        {activeTab === 'AI Providers' && (
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="text-sm font-medium text-foreground mb-2">AI Provider</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Keys are stored by the local backend and are never shown again after saving.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-5">
              {providers.map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => settings.setProvider(id)}
                  className={cn(
                    'rounded-md border px-3 py-2 text-xs font-medium transition-colors',
                    settings.provider === id
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:text-foreground'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Model</label>
                <input
                  value={settings.model}
                  onChange={(event) => settings.setModel(event.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              {settings.provider === 'ollama' && (
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">Ollama Base URL</label>
                  <input
                    value={settings.baseUrl}
                    onChange={(event) => settings.setBaseUrl(event.target.value)}
                    placeholder="http://localhost:11434"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              )}
              {settings.provider !== 'ollama' && (
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">API Key</label>
                  <input
                    type="password"
                    value={settings.apiKey}
                    onChange={(event) => settings.setApiKey(event.target.value)}
                    placeholder={settings.aiConfig?.provider === settings.provider && settings.aiConfig.hasApiKey ? 'Saved key configured' : 'Enter provider API key'}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              )}
            </div>
            {settings.error && <p className="mt-4 text-sm text-destructive">{settings.error}</p>}
            {settings.statusMessage && <p className="mt-4 text-sm text-success">{settings.statusMessage}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={settings.testAiConfig} disabled={settings.testing} className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-50 transition-colors">
                {settings.testing ? 'Testing...' : 'Test Connection'}
              </button>
              <button onClick={settings.saveAiConfig} disabled={settings.loading} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
                {settings.loading ? 'Saving...' : 'Save Provider'}
              </button>
            </div>
          </div>
        )}
        {activeTab === 'Appearance' && (
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="text-sm font-medium text-foreground mb-4">Theme</h3>
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 rounded-md border-2 border-primary bg-card px-4 py-3 text-sm font-medium">
                <div className="h-4 w-4 rounded-full bg-[#0a0e1a]" />
                Dark
              </button>
              <button disabled className="flex items-center gap-2 rounded-md border border-border bg-card px-4 py-3 text-sm font-medium text-muted-foreground cursor-not-allowed">
                <div className="h-4 w-4 rounded-full bg-white border border-border" />
                Light (Coming Soon)
              </button>
            </div>
          </div>
        )}
        {activeTab === 'Notifications' && (
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="text-sm font-medium text-foreground mb-4">Notification Preferences</h3>
            <div className="space-y-4">
              {['Analysis complete', 'Error alerts', 'New insights available'].map((item) => (
                <div key={item} className="flex items-center justify-between">
                  <span className="text-sm text-foreground">{item}</span>
                  <button disabled className="relative h-5 w-9 rounded-full bg-muted transition-colors cursor-not-allowed">
                    <div className="absolute right-0.5 top-0.5 h-4 w-4 rounded-full bg-primary-foreground transition-transform" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {activeTab === 'API Keys' && (
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="text-sm font-medium text-foreground mb-2">API Keys</h3>
            <p className="text-xs text-muted-foreground mb-4">Manage API keys for programmatic access.</p>
            <div className="flex items-center justify-center py-8">
              <p className="text-sm text-muted-foreground">No API keys configured.</p>
            </div>
            <div className="flex justify-end">
              <button disabled className="rounded-md bg-muted px-4 py-2 text-sm font-medium text-muted-foreground cursor-not-allowed">
                Coming Soon
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
