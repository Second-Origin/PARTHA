import { useEffect, useMemo } from 'react';
import { useAuthStore } from '@/app/store/useAuthStore';
import { LandingCanvas, LandingNavProvider, type LandingNav } from '@/features/landing/components/LandingCanvas';
import { LandingScaler } from '@/features/landing/components/LandingScaler';
import { useLandingTheme } from '@/features/landing/hooks/useLandingTheme';

/** Where to send someone who asks to get in touch. */
const CONTACT_URL = 'https://discord.gg/qvk9DcxDA';

/**
 * The marketing page, rendered as the iteration-1 design canvas in real DOM.
 *
 * It used to be the authored 1728-wide artwork exported as a single flat SVG
 * (6.5 MB across the light and dark cuts) with transparent hotspots laid over
 * it. That preserved the composition but nothing in it was real: no selectable
 * text, no focusable controls, the carousels could not move, and the FAQ
 * opened a modal because the accordion could not expand in place.
 * `LandingCanvas` is the same composition as elements -- the design's own
 * geometry and colours -- so the pieces the design specified as interactive
 * now behave: the product card cycles through its three states, the
 * capabilities carousel advances, the FAQ expands, and the footer switch
 * drives the theme.
 *
 * `LandingScaler` renders it at its authored 1728px width and scales to the
 * viewport, so proportions stay exactly as signed off.
 *
 * The .landing-dark class is applied to this component's own root element
 * only, never to <html> (see useLandingTheme.ts and globals.css) -- it cannot
 * leak into /login, /register, or any authenticated route, and cleans itself
 * up on unmount since it is plain conditional JSX, not DOM mutation.
 */
export function LandingPage() {
  const authenticated = useAuthStore((state) => state.status === 'authenticated');
  const theme = useLandingTheme();
  const dark = theme.resolved === 'dark';

  useEffect(() => {
    // Hand off from the pre-hydration boot flash-guard (index.html) to this
    // component's own scoped class now that React has mounted.
    document.documentElement.removeAttribute('data-landing-theme-boot');
  }, []);

  /* Self-hosted is the only deployment model for the foreseeable future
   * (#382): an unauthenticated visitor's "analyze a repository" intent goes
   * straight to account creation on this instance, same as it would for
   * anyone standing up their own copy of PARTHA. Registration still enforces
   * the admin-managed email allowlist (#374/#375) or the development bypass
   * (#384) exactly as before -- this only decides where the CTA points. */
  const nav = useMemo<LandingNav>(
    () => ({
      analyze: authenticated ? '/upload' : '/register',
      login: authenticated ? '/dashboard' : '/login',
      register: authenticated ? '/dashboard' : '/register',
      contact: CONTACT_URL,
      docs: '/documentation',
    }),
    [authenticated],
  );

  return (
    <main
      className={
        dark
          ? 'landing-dark min-h-screen bg-background text-foreground'
          : 'min-h-screen bg-background text-foreground'
      }
    >
      <h1 className="sr-only">Reveal the system behind the code.</h1>
      <LandingNavProvider value={nav}>
        <LandingScaler>
          <LandingCanvas />
        </LandingScaler>
      </LandingNavProvider>
    </main>
  );
}
