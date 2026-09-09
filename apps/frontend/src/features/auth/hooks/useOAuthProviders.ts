import { useEffect, useState } from 'react';
import { authService } from '@/shared/services/api';
import type { OAuthProvider } from '@/shared/services/api/types';

/** Which OAuth providers the backend actually has real credentials
 * configured for (#288) -- the same capability-gating idea as the AI
 * provider setup metadata: never render a button for a provider that isn't
 * live. Starts empty (no flash of buttons that then disappear) and stays
 * empty, silently, if the check itself fails -- a broken capability check
 * should degrade to "no OAuth buttons," never block password sign-in. */
export function useOAuthProviders() {
  const [providers, setProviders] = useState<OAuthProvider[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    authService
      .getOAuthProviders()
      .then((response) => {
        if (!cancelled) setProviders(response.providers as OAuthProvider[]);
      })
      .catch(() => {
        // Deliberately silent -- see the module doc above.
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { providers, loaded };
}
