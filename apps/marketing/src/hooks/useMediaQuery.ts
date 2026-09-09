import { useCallback, useSyncExternalStore } from 'react';

/** Track a CSS media query via the browser's own matchMedia store. Read
 * synchronously on first render (client-only Vite SPA) so there is no
 * first-paint flash between the two landing layouts. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      const media = window.matchMedia(query);
      media.addEventListener('change', onStoreChange);
      // Belt-and-braces: a few engines (and emulated devtools viewports) don't
      // fire MediaQueryList 'change' reliably. useSyncExternalStore only
      // re-renders when the boolean snapshot actually flips, so the extra
      // resize events are cheap.
      window.addEventListener('resize', onStoreChange);
      return () => {
        media.removeEventListener('change', onStoreChange);
        window.removeEventListener('resize', onStoreChange);
      };
    },
    [query],
  );

  const getSnapshot = useCallback(() => window.matchMedia(query).matches, [query]);

  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
