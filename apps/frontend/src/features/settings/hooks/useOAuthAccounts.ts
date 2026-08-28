import { useCallback, useEffect, useState } from 'react';
import { authService, getErrorMessage } from '@/shared/services/api';
import type { OAuthLinkedIdentity, OAuthProvider } from '@/shared/services/api/types';
import { useOAuthProviders } from '@/features/auth/hooks/useOAuthProviders';

/** Settings' "Connected accounts" card (#288): lists the caller's linked
 * Google/GitHub identities and lets them link one more (via a full-page
 * redirect the same as sign-in) or unlink one they no longer want.
 *
 * Linking reuses the exact /oauth/{provider}/callback -> /oauth/complete
 * round trip sign-in uses, just with intent=link; nothing about the
 * redirect flow is special-cased for Settings. */
export function useOAuthAccounts() {
  const { providers: availableProviders } = useOAuthProviders();
  const [identities, setIdentities] = useState<OAuthLinkedIdentity[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<OAuthProvider | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const reload = useCallback(() => {
    authService
      .listLinkedOAuthIdentities()
      .then((response) => setIdentities(response.identities))
      .catch((caught) => setLoadError(getErrorMessage(caught)));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const link = useCallback(async (provider: OAuthProvider) => {
    if (pendingAction) return;
    setPendingAction(provider);
    setActionError(null);
    try {
      const { authorizeUrl } = await authService.startOAuthLink(provider);
      window.location.assign(authorizeUrl);
    } catch (caught) {
      setActionError(getErrorMessage(caught));
      setPendingAction(null);
    }
    // No `finally` clearing pendingAction on the success path: the page is
    // navigating away.
  }, [pendingAction]);

  const unlink = useCallback(
    async (provider: OAuthProvider) => {
      if (pendingAction) return;
      setPendingAction(provider);
      setActionError(null);
      try {
        await authService.unlinkOAuthProvider(provider);
        reload();
      } catch (caught) {
        setActionError(getErrorMessage(caught));
      } finally {
        setPendingAction(null);
      }
    },
    [pendingAction, reload],
  );

  const linkedProviders = new Set((identities ?? []).map((identity) => identity.provider));
  const unlinkedAvailableProviders = availableProviders.filter((provider) => !linkedProviders.has(provider));

  return {
    identities,
    loadError,
    linkableProviders: unlinkedAvailableProviders,
    pendingAction,
    actionError,
    link,
    unlink,
  };
}
