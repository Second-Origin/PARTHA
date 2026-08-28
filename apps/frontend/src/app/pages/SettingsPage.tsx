import { Loader2 } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { useSettings } from '@/features/settings/hooks/useSettings';
import { useAccountDeletion } from '@/features/settings/hooks/useAccountDeletion';
import { useOAuthAccounts } from '@/features/settings/hooks/useOAuthAccounts';
import { useAuthStore } from '@/app/store/useAuthStore';
import { cn } from '@/shared/utils/cn';

const OAUTH_PROVIDER_LABEL: Record<string, string> = { google: 'Google', github: 'GitHub' };

export function SettingsPage() {
  const settings = useSettings();
  const { tabs, activeTab, setActiveTab } = settings;
  const user = useAuthStore((state) => state.user);
  const deletion = useAccountDeletion();
  const oauthAccounts = useOAuthAccounts();

  return (
    <div className="w-full max-w-4xl">
      <PageHeader title="Settings" description="Manage your account and preferences" />

      <div role="tablist" aria-label="Settings sections" className="mb-7 flex max-w-full items-center gap-1 overflow-x-auto border-b border-primary/15 scrollbar-thin">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'relative rounded-t-xl px-4 py-3 text-sm font-semibold transition-colors',
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
            <div className="rounded-3xl border border-primary/20 bg-card p-6 shadow-[0_14px_34px_hsl(var(--foreground)/0.04)]">
              <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-primary">Account</p><h2 className="mt-1 text-lg font-semibold text-foreground mb-4">Your profile</h2>
              <div className="space-y-4">
                <div>
                  <label htmlFor="settings-email" className="block text-xs font-medium text-muted-foreground mb-1.5">Email</label>
                  <input
                    id="settings-email"
                    type="email"
                    value={user?.email ?? ''}
                    disabled
                    className="w-full rounded-xl border border-primary/20 bg-background px-3 py-2.5 text-sm text-foreground disabled:opacity-70"
                  />
                </div>
                <div>
                  <label htmlFor="settings-member-since" className="block text-xs font-medium text-muted-foreground mb-1.5">Member Since</label>
                  <input
                    id="settings-member-since"
                    type="text"
                    value={user ? new Date(user.createdAt).toLocaleDateString() : ''}
                    disabled
                    className="w-full rounded-xl border border-primary/20 bg-background px-3 py-2.5 text-sm text-foreground disabled:opacity-70"
                  />
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button disabled className="rounded-xl bg-muted px-4 py-2.5 text-sm font-semibold text-muted-foreground cursor-not-allowed">
                  Editing Coming Soon
                </button>
              </div>
            </div>
            {(oauthAccounts.identities === null ? [] : oauthAccounts.identities).length > 0 ||
            oauthAccounts.linkableProviders.length > 0 ? (
              <div className="rounded-3xl border border-primary/20 bg-card p-6 shadow-[0_14px_34px_hsl(var(--foreground)/0.04)]">
                <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-primary">Sign-in</p>
                <h2 className="mt-1 text-lg font-semibold text-foreground mb-4">Connected accounts</h2>
                <div className="space-y-3">
                  {(oauthAccounts.identities ?? []).map((identity) => (
                    <div
                      key={identity.provider}
                      className="flex items-center justify-between rounded-xl border border-primary/15 bg-background px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {OAUTH_PROVIDER_LABEL[identity.provider] ?? identity.provider}
                        </p>
                        {identity.email && <p className="text-xs text-muted-foreground">{identity.email}</p>}
                      </div>
                      <button
                        type="button"
                        onClick={() => oauthAccounts.unlink(identity.provider as 'google' | 'github')}
                        disabled={oauthAccounts.pendingAction !== null}
                        className="rounded-xl border border-primary/20 px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-accent disabled:opacity-50 transition-colors"
                      >
                        {oauthAccounts.pendingAction === identity.provider ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          'Unlink'
                        )}
                      </button>
                    </div>
                  ))}
                  {oauthAccounts.linkableProviders.map((provider) => (
                    <div
                      key={provider}
                      className="flex items-center justify-between rounded-xl border border-dashed border-primary/20 bg-background px-4 py-3"
                    >
                      <p className="text-sm font-medium text-muted-foreground">
                        {OAUTH_PROVIDER_LABEL[provider] ?? provider}
                      </p>
                      <button
                        type="button"
                        onClick={() => oauthAccounts.link(provider)}
                        disabled={oauthAccounts.pendingAction !== null}
                        className="rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                      >
                        {oauthAccounts.pendingAction === provider ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          'Link'
                        )}
                      </button>
                    </div>
                  ))}
                </div>
                {oauthAccounts.actionError && (
                  <p role="alert" className="mt-3 text-sm text-destructive">
                    {oauthAccounts.actionError}
                  </p>
                )}
              </div>
            ) : null}
            <div className="rounded-3xl border border-destructive/50 bg-card p-6 shadow-[0_14px_34px_hsl(var(--foreground)/0.04)]">
              <h2 className="text-sm font-medium text-destructive mb-2">Danger Zone</h2>
              <p className="text-xs text-muted-foreground mb-4">
                Permanently delete your account, repositories, AI provider configuration, and conversation history.
                This cannot be undone.
              </p>
              {!deletion.expanded && (
                <button
                  type="button"
                  onClick={deletion.open}
                  className="rounded-xl border border-destructive/50 px-4 py-2.5 text-sm font-semibold text-destructive hover:bg-destructive/10 transition-colors"
                >
                  Delete Account
                </button>
              )}
              {deletion.expanded && (
                <div className="space-y-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                  <div>
                    <label htmlFor="delete-confirm-email" className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Type <span className="font-mono text-foreground">{deletion.email}</span> to confirm
                    </label>
                    <input
                      id="delete-confirm-email"
                      type="email"
                      value={deletion.confirmEmail}
                      onChange={(event) => deletion.setConfirmEmail(event.target.value)}
                      autoComplete="off"
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-destructive"
                    />
                  </div>
                  <div>
                    <label htmlFor="delete-confirm-password" className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Password
                    </label>
                    <input
                      id="delete-confirm-password"
                      type="password"
                      value={deletion.password}
                      onChange={(event) => deletion.setPassword(event.target.value)}
                      autoComplete="current-password"
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-destructive"
                    />
                  </div>
                  {deletion.error && <p role="alert" className="text-sm text-destructive">{deletion.error}</p>}
                  <div className="flex flex-wrap justify-end gap-2">
                    <button
                      type="button"
                      onClick={deletion.cancel}
                      disabled={deletion.submitting}
                      className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={deletion.deleteAccount}
                      disabled={!deletion.canSubmit}
                      className="rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
                    >
                      {deletion.submitting ? 'Deleting...' : 'Permanently Delete Account'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        {activeTab === 'AI Providers' && (
          <div className="partha-surface p-4 sm:p-6">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-medium text-foreground">AI Provider</h2>
              <span className={cn(
                'rounded-full px-2.5 py-1 text-xs font-medium',
                settings.aiConfig?.provider
                  ? 'bg-success/10 text-success'
                  : 'bg-muted text-muted-foreground',
              )}>
                {settings.aiConfig?.provider ? `Saved: ${settings.aiConfig.provider}` : 'Not configured'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mb-4">
              Keys are stored by the local backend, encrypted at rest, and are never shown again after saving.
            </p>
            {settings.capabilitiesError && (
              <p role="alert" className="mb-4 text-sm text-destructive">{settings.capabilitiesError}</p>
            )}
            <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              {settings.capabilities.map((capability) => (
                <button
                  key={capability.provider}
                  type="button"
                  aria-pressed={settings.provider === capability.provider}
                  onClick={() => settings.setProvider(capability.provider)}
                  className={cn(
                    'rounded-md border px-3 py-2 text-xs font-medium transition-colors',
                    settings.provider === capability.provider
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:text-foreground'
                  )}
                >
                  {capability.displayName}
                </button>
              ))}
            </div>
            {settings.activeCapability && (
              <div className="mb-5 rounded-md border border-border bg-muted/40 p-3">
                <p className="text-xs font-medium text-foreground mb-1.5">
                  Getting started with {settings.activeCapability.displayName}
                </p>
                <ol className="list-decimal space-y-1 pl-4 text-xs text-muted-foreground">
                  {settings.activeCapability.setupSteps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
                <a
                  href={settings.activeCapability.setupUrl}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
                >
                  Open {settings.activeCapability.displayName} setup page
                </a>
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label htmlFor="settings-model" className="block text-xs font-medium text-muted-foreground mb-1.5">Provider model ID</label>
                <input
                    id="settings-model"
                  value={settings.model}
                  onChange={(event) => settings.setModel(event.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              {settings.activeCapability?.requiresBaseUrl && (
                <div>
                  <label htmlFor="settings-base-url" className="block text-xs font-medium text-muted-foreground mb-1.5">
                    {settings.activeCapability.displayName} Base URL
                  </label>
                  <input
                    id="settings-base-url"
                    value={settings.baseUrl}
                    onChange={(event) => settings.setBaseUrl(event.target.value)}
                    placeholder="http://localhost:11434"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              )}
              {settings.activeCapability?.requiresApiKey && (
                <div>
                  <label htmlFor="settings-api-key" className="block text-xs font-medium text-muted-foreground mb-1.5">API Key</label>
                  <input
                    id="settings-api-key"
                    type="password"
                    value={settings.apiKey}
                    onChange={(event) => settings.setApiKey(event.target.value)}
                    placeholder={
                      settings.aiConfig?.provider === settings.provider && settings.aiConfig.hasApiKey
                        ? settings.aiConfig.apiKeyLast4
                          ? `Saved key •••• ${settings.aiConfig.apiKeyLast4}`
                          : 'Saved key configured'
                        : 'Enter provider API key'
                    }
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
              )}
            </div>
            {settings.error && <p className="mt-4 text-sm text-destructive">{settings.error}</p>}
            {settings.statusMessage && <p className="mt-4 text-sm text-success">{settings.statusMessage}</p>}
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={settings.testAiConfig} disabled={settings.testing || settings.loading} className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-50 transition-colors">
                {settings.testing ? 'Testing...' : 'Test Connection'}
              </button>
              <button type="button" onClick={settings.saveAiConfig} disabled={settings.loading || settings.testing} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
                {settings.loading ? 'Saving...' : 'Save Provider'}
              </button>
            </div>
          </div>
        )}
        {activeTab === 'Notifications' && (
          <div className="rounded-3xl border border-primary/20 bg-card p-6 shadow-[0_14px_34px_hsl(var(--foreground)/0.04)]">
            <div className="mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-medium text-foreground">Notification Preferences</h2>
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                  Coming Soon
                </span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Notification preferences are in development and cannot be configured yet.
              </p>
            </div>
            <div className="space-y-4">
              {['Analysis complete', 'Error alerts', 'New insights available'].map((item) => (
                <div key={item} className="flex items-center justify-between">
                  <span className="text-sm text-foreground">{item}</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked="false"
                    aria-label={`${item} notifications (coming soon)`}
                    disabled
                    className="relative h-5 w-9 rounded-full bg-muted transition-colors cursor-not-allowed"
                  >
                    <div
                      aria-hidden="true"
                      className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-primary-foreground transition-transform"
                    />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {activeTab === 'API Keys' && (
          <div className="rounded-3xl border border-primary/20 bg-card p-6 shadow-[0_14px_34px_hsl(var(--foreground)/0.04)]">
            <h2 className="text-sm font-medium text-foreground mb-2">API Keys</h2>
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
