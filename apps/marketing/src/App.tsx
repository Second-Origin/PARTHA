import { useEffect, useState } from 'react';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { useLandingTheme } from '@/hooks/useLandingTheme';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { DemoModal } from '@/components/DemoModal';
import { RunItYourselfModal } from '@/components/RunItYourselfModal';
import { MobileLanding } from '@/components/MobileLanding';
import { Modal } from '@/components/Modal';
import { faqAnswers, faqQuestions } from '@/data/faq';
import { FOOTER_COLUMNS, type FooterLink } from '@/data/site';
import landingReference from '@/assets/landing/landing-reference.svg';
import landingReferenceDark from '@/assets/landing/landing-reference-dark.svg';

/**
 * Adapted from apps/frontend/src/app/pages/LandingPage.tsx (#382 redesign):
 * the real, signed-off marketing page -- same 1728-wide authored design
 * canvas, same light/dark theme system, same FAQ and footer. Two behavioral
 * differences from the real app, since this standalone site has no backend
 * and no accounts at all:
 *
 * - The nav's "Log in" hotspot and the hero's "See how it works" hotspot
 *   both open the scripted demo simulation (DemoModal).
 * - Every "Analyze a Repository" hotspot opens local setup instructions
 *   (RunItYourselfModal) -- there is no live backend to analyze against.
 *
 * The authored canvas is a fixed 1728-wide composition: on a narrow screen
 * it only shrinks, so its text becomes unreadable. At >= 1024px this renders
 * that canvas; below it, a real responsive layout (MobileLanding) with the
 * same content and the same dialogs. Only one of the two is ever in the DOM,
 * so the 3.3 MB design SVG never loads on a phone.
 */
export function App() {
  const [faqIndex, setFaqIndex] = useState<number | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);
  const [runItYourselfOpen, setRunItYourselfOpen] = useState(false);
  const theme = useLandingTheme();
  const dark = theme.resolved === 'dark';
  const isDesktop = useMediaQuery('(min-width: 1024px)');

  useEffect(() => {
    document.documentElement.removeAttribute('data-landing-theme-boot');
  }, []);

  const analyzeCta = (className: string) => (
    <button type="button" className={`${className} border-0 bg-transparent p-0`} onClick={() => setRunItYourselfOpen(true)}>
      <span className="sr-only">Run PARTHA on your own repository</span>
    </button>
  );

  return (
    <main className={dark ? 'landing-dark min-h-screen bg-background text-foreground' : 'min-h-screen bg-background text-foreground'}>
      <h1 className="sr-only">Reveal the system behind the code.</h1>

      {isDesktop ? (
        <div className="relative mx-auto w-full max-w-[1728px]">
          <img
            src={dark ? landingReferenceDark : landingReference}
            alt="PARTHA repository intelligence system overview, capabilities, frequently asked questions, and call to action."
            className="block h-auto w-full select-none"
            draggable="false"
          />

          <ThemeSwitcher
            preference={theme.preference}
            onChange={theme.setPreference}
            className="pointer-events-auto absolute right-[9.75%] top-[98.42%] z-20"
          />

          <nav aria-label="PARTHA marketing navigation" className="pointer-events-none absolute inset-0 z-20">
            <a className="pointer-events-auto absolute left-[28.5%] top-[0.45%] h-[1.15%] w-[7.5%]" href="#product"><span className="sr-only">Product</span></a>
            <a className="pointer-events-auto absolute left-[37%] top-[0.45%] h-[1.15%] w-[8.5%]" href="#how-it-works"><span className="sr-only">How it works</span></a>
            <a className="pointer-events-auto absolute left-[46.2%] top-[0.45%] h-[1.15%] w-[9.2%]" href="#capabilities"><span className="sr-only">Capabilities</span></a>
            <a className="pointer-events-auto absolute left-[56.5%] top-[0.45%] h-[1.15%] w-[4.5%]" href="#faq"><span className="sr-only">Frequently asked questions</span></a>
            <button
              type="button"
              className="pointer-events-auto absolute left-[76%] top-[0.45%] h-[1.15%] w-[5.8%] border-0 bg-transparent p-0"
              onClick={() => setDemoOpen(true)}
            >
              <span className="sr-only">See a scripted demo</span>
            </button>
            {analyzeCta('pointer-events-auto absolute left-[82%] top-[0.35%] h-[1.35%] w-[11%]')}
          </nav>

          <div id="product" className="absolute left-0 top-[18.5%]" />
          <div id="how-it-works" className="absolute left-0 top-[43.9%]" />
          <div id="capabilities" className="absolute left-0 top-[60.5%]" />
          <div id="faq" className="absolute left-0 top-[72.5%]" />

          <button
            type="button"
            className="absolute left-[28.2%] top-[13.5%] z-20 h-[1.35%] w-[19.1%] border-0 bg-transparent p-0"
            onClick={() => setDemoOpen(true)}
          >
            <span className="sr-only">See a scripted demo of PARTHA in action</span>
          </button>
          {analyzeCta('absolute left-[49.4%] top-[13.5%] z-20 h-[1.35%] w-[22.4%]')}

          {faqQuestions.map((question, index) => (
            <button
              key={question}
              type="button"
              aria-label={question}
              onClick={() => setFaqIndex(index)}
              className="absolute left-[31.1%] z-20 h-[0.92%] w-[64.1%] border-0 bg-transparent p-0"
              style={{ top: `${74.9 + index * 1.04}%` }}
            />
          ))}

          {analyzeCta('absolute left-[36.1%] top-[87.55%] z-20 h-[1.3%] w-[14.8%]')}
          <a className="absolute left-[51%] top-[87.55%] z-20 h-[1.3%] w-[14.8%]" href="https://discord.gg/qvk9DcxDA" target="_blank" rel="noreferrer"><span className="sr-only">Get in touch with PARTHA</span></a>

          <a className="absolute left-[6.2%] top-[91.9%] z-20 h-[4.3%] w-[22.4%]" href="/" aria-label="PARTHA home" />

          {footerControls.map((item) => (
            <FooterControl key={item.label} item={item} />
          ))}
        </div>
      ) : (
        <MobileLanding
          theme={theme}
          onOpenDemo={() => setDemoOpen(true)}
          onOpenRunItYourself={() => setRunItYourselfOpen(true)}
        />
      )}

      {faqIndex !== null && (
        <Modal onClose={() => setFaqIndex(null)} labelledBy="landing-faq-title" maxWidthClassName="max-w-xl">
          <div className="p-6 sm:p-8">
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">FAQ</p>
                <h2 id="landing-faq-title" className="font-display mt-2 text-2xl font-semibold text-foreground">{faqQuestions[faqIndex]}</h2>
              </div>
              <button type="button" onClick={() => setFaqIndex(null)} className="rounded-xl border border-primary/30 px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent">Close</button>
            </div>
            <p className="mt-5 text-base leading-relaxed text-muted-foreground">{faqAnswers[faqIndex]}</p>
          </div>
        </Modal>
      )}

      {demoOpen && <DemoModal onClose={() => setDemoOpen(false)} />}
      {runItYourselfOpen && <RunItYourselfModal onClose={() => setRunItYourselfOpen(false)} />}
    </main>
  );
}

// Desktop overlay only: the authored footer sits at fixed positions in the
// 1728-wide canvas. Columns are 39.1 / 55 / 70.6 / 86.3 % from the left; rows
// step down 0.8 % each. Derived from FOOTER_COLUMNS so the link set stays a
// single source of truth shared with MobileLanding.
const FOOTER_COLUMN_LEFT = ['39.1%', '55%', '70.6%', '86.3%'] as const;
const FOOTER_ROW_TOP = ['93.65%', '94.45%', '95.25%', '96.05%'] as const;

type PositionedFooterLink = FooterLink & { left: string; top: string };

const footerControls: PositionedFooterLink[] = FOOTER_COLUMNS.flatMap((column, columnIndex) =>
  column.links.map((link, rowIndex) => ({
    ...link,
    left: FOOTER_COLUMN_LEFT[columnIndex],
    top: FOOTER_ROW_TOP[rowIndex],
  })),
);

function FooterControl({ item }: { item: PositionedFooterLink }) {
  return (
    <a
      aria-label={item.label}
      className="absolute z-20 h-[0.9%] w-[10.5%] border-0 bg-transparent p-0"
      style={{ left: item.left, top: item.top }}
      href={item.href}
      target={item.external ? '_blank' : undefined}
      rel={item.external ? 'noreferrer' : undefined}
    />
  );
}
