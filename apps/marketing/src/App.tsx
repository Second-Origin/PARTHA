import { useEffect, useState } from 'react';

import { DemoModal } from '@/components/DemoModal';
import { RunItYourselfModal } from '@/components/RunItYourselfModal';
import { Capabilities } from '@/components/landing/Capabilities';
import { CtaBand } from '@/components/landing/CtaBand';
import { Faq } from '@/components/landing/Faq';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { Hero } from '@/components/landing/Hero';
import { SiteFooter } from '@/components/landing/SiteFooter';
import { SiteHeader } from '@/components/landing/SiteHeader';
import { StoryCards } from '@/components/landing/StoryCards';
import { useLandingTheme } from '@/hooks/useLandingTheme';

/**
 * The PARTHA marketing site, built from the iteration-1 landing design
 * (Figma f1HlSxjl8pvvOm86XFPZEJ, frame "Landing Page").
 *
 * This is a real implementation of that design, not a picture of it. The
 * previous version rendered a 3.3 MB flat SVG export of the same frame with
 * invisible percentage-positioned hotspots on top, which meant nothing the
 * designer specified as interactive actually was: the capability carousel
 * never advanced, the FAQ opened a modal instead of expanding, there were no
 * hover or focus states, and the page carried no real text for search engines
 * or screen readers. Every section here is composed from the design's own
 * illustration exports instead.
 *
 * Two behavioural differences from the product, since this standalone site has
 * no backend and no accounts:
 *
 * - "Log In" and "See how it works" open the scripted demo (DemoModal).
 * - Every "Analyze a Repository" opens local setup instructions
 *   (RunItYourselfModal) -- there is no live backend to analyse against.
 */
export function App() {
  const [demoOpen, setDemoOpen] = useState(false);
  const [runItYourselfOpen, setRunItYourselfOpen] = useState(false);
  const theme = useLandingTheme();
  const dark = theme.resolved === 'dark';

  useEffect(() => {
    document.documentElement.removeAttribute('data-landing-theme-boot');
  }, []);

  const openDemo = () => setDemoOpen(true);
  const openRunItYourself = () => setRunItYourselfOpen(true);

  return (
    <div className={dark ? 'landing-dark min-h-screen bg-background text-foreground' : 'min-h-screen bg-background text-foreground'}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:font-display focus:text-sm focus:font-semibold focus:text-white"
      >
        Skip to content
      </a>

      <SiteHeader onLogIn={openDemo} onCreateAccount={openRunItYourself} />

      <main id="main">
        <Hero onAnalyze={openRunItYourself} onSeeHowItWorks={openDemo} />
        <StoryCards />
        <HowItWorks />
        <Capabilities />
        <Faq />
        <CtaBand onAnalyze={openRunItYourself} />
      </main>

      <SiteFooter themePreference={theme.preference} onThemeChange={theme.setPreference} />

      {demoOpen && <DemoModal onClose={() => setDemoOpen(false)} />}
      {runItYourselfOpen && <RunItYourselfModal onClose={() => setRunItYourselfOpen(false)} />}
    </div>
  );
}
