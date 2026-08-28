import { useState } from 'react';
import { Github, Loader2 } from 'lucide-react';
import { authService, getErrorMessage } from '@/shared/services/api';
import type { OAuthProvider } from '@/shared/services/api/types';
import { useOAuthProviders } from '../hooks/useOAuthProviders';

const PROVIDER_LABEL: Record<OAuthProvider, string> = {
  google: 'Google',
  github: 'GitHub',
};

function GoogleGlyph() {
  return (
    <svg viewBox="0 0 18 18" className="h-4 w-4" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.88 2.7-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.9v2.33A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.9A9 9 0 0 0 0 9c0 1.45.35 2.83.9 4.03z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .9 4.97L3.95 7.3C4.66 5.17 6.65 3.58 9 3.58z" />
    </svg>
  );
}

/** "Continue with Google/GitHub" buttons for the Login page (#288).
 *
 * Login-page only, deliberately not on Register: the backend does not yet
 * create a brand-new account over OAuth (that would bypass the invite-code
 * gate registration otherwise enforces -- see the comment on issue #288).
 * These buttons cover signing in to an existing account and the
 * password-confirmed linking flow for one whose email matches; a visitor
 * with no PARTHA account yet still needs an invite code and the password
 * form.
 *
 * Renders nothing (not even a placeholder) until the capability check
 * resolves, and nothing at all if neither provider is configured -- password
 * auth remains fully usable either way. */
export function OAuthButtons() {
  const { providers } = useOAuthProviders();
  const [pending, setPending] = useState<OAuthProvider | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (providers.length === 0) return null;

  const start = async (provider: OAuthProvider) => {
    if (pending) return;
    setPending(provider);
    setError(null);
    try {
      const { authorizeUrl } = await authService.startOAuthLogin(provider);
      window.location.assign(authorizeUrl);
      // Intentionally no `finally` clearing `pending`: the page is
      // navigating away, and leaving the button disabled avoids a flash of
      // it becoming clickable again during that navigation.
    } catch (caught) {
      setError(getErrorMessage(caught));
      setPending(null);
    }
  };

  return (
    <div className="mb-5 space-y-3">
      {providers.map((provider) => (
        <button
          key={provider}
          type="button"
          onClick={() => start(provider)}
          disabled={pending !== null}
          data-testid={`oauth-button-${provider}`}
          className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-primary/25 bg-card px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
        >
          {pending === provider ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : provider === 'github' ? (
            <Github className="h-4 w-4" />
          ) : (
            <GoogleGlyph />
          )}
          Continue with {PROVIDER_LABEL[provider]}
        </button>
      ))}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3 pt-1 text-2xs uppercase tracking-[0.14em] text-muted-foreground">
        <span className="h-px flex-1 bg-primary/15" />
        or
        <span className="h-px flex-1 bg-primary/15" />
      </div>
    </div>
  );
}
