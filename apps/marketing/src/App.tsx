import { useEffect, useState } from 'react';

import { DemoModal } from '@/components/DemoModal';
import { RunItYourselfModal } from '@/components/RunItYourselfModal';
import { LandingCanvas } from '@/components/landing/LandingCanvas';
import { SiteHeader } from '@/components/landing/SiteHeader';
import { LandingScaler } from '@/components/landing/LandingScaler';
import { useLandingTheme } from '@/hooks/useLandingTheme';

/**
 * The PARTHA marketing site.
 *
 * The page body is the iteration-1 Figma frame ported as real DOM
 * (`LandingCanvas`), rendered at its authored 1728px width and scaled to the
 * viewport by `LandingScaler`. The geometry is the design's own -- this is not
 * a responsive re-interpretation of it.
 *
 * It replaces a 3.3 MB flat SVG export of the same frame with invisible
 * hotspots on top, so the text is now real, controls are focusable, and the
 * pieces the design specified as interactive can actually behave.
 *
 * The two hero calls to action open full-screen panels over the page rather
 * than navigating away: "See how it works" runs a scripted walkthrough of a
 * real analysis, and "Analyze a Repository" shows how to run PARTHA against
 * your own code. Closing either returns the reader exactly where they were.
 */
/** The band the design spends on its own header, which `SiteHeader` replaces. */
const CANVAS_HEADER_HEIGHT = 133;

export function App() {
  const [demoOpen, setDemoOpen] = useState(false);
  const [runItYourselfOpen, setRunItYourselfOpen] = useState(false);
  const theme = useLandingTheme();
  const dark = theme.resolved === 'dark';

  useEffect(() => {
    document.documentElement.removeAttribute('data-landing-theme-boot');
  }, []);

  return (
    <div className={dark ? 'landing-dark min-h-screen bg-background' : 'min-h-screen bg-background'}>
      <SiteHeader />
      <LandingScaler cropTop={CANVAS_HEADER_HEIGHT}>
        <LandingCanvas
          onSeeHowItWorks={() => setDemoOpen(true)}
          onAnalyzeRepository={() => setRunItYourselfOpen(true)}
        />
      </LandingScaler>

      {demoOpen && <DemoModal onClose={() => setDemoOpen(false)} />}
      {runItYourselfOpen && <RunItYourselfModal onClose={() => setRunItYourselfOpen(false)} />}
    </div>
  );
}
