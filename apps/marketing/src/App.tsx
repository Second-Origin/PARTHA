import { useEffect, useState } from 'react';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { useLandingTheme } from '@/hooks/useLandingTheme';
import { DemoModal } from '@/components/DemoModal';
import { RunItYourselfModal } from '@/components/RunItYourselfModal';
import { Modal } from '@/components/Modal';
import landingReference from '@/assets/landing/landing-reference.svg';
import landingReferenceDark from '@/assets/landing/landing-reference-dark.svg';

/**
 * Adapted from apps/frontend/src/app/pages/LandingPage.tsx (#382 redesign):
 * the real, signed-off marketing page -- same 1728-wide authored design
 * canvas, same light/dark theme system, same FAQ and footer -- reused
 * directly rather than re-invented, per the project owner's explicit
 * direction. Two behavioral differences from the real app, since this
 * standalone site has no backend and no accounts at all:
 *
 * - The nav's "Log in" hotspot and the hero's "See how it works" hotspot
 *   both open the scripted demo simulation (DemoModal) instead of a dead
 *   login route / an anchor scroll -- seeing PARTHA "work" here means
 *   watching the simulation, since there's nothing live to log into.
 * - Every "Analyze a Repository" hotspot has nothing to analyze against
 *   (no live backend), so it opens setup instructions for running the real
 *   product locally (RunItYourselfModal) instead.
 *
 * Everything else -- the artwork, the FAQ, the footer, the theme toggle --
 * is the same interaction shape as the real page. The demo, run-it-yourself,
 * and FAQ dialogs all share the Modal container: a centered card over a
 * dimmed backdrop, which keeps the reused landing artwork's own length and
 * layout untouched.
 */
export function App() {
  const [faqIndex, setFaqIndex] = useState<number | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);
  const [runItYourselfOpen, setRunItYourselfOpen] = useState(false);
  const theme = useLandingTheme();
  const dark = theme.resolved === 'dark';

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

        {faqIndex !== null && (
          <Modal onClose={() => setFaqIndex(null)} labelledBy="landing-faq-title" maxWidthClassName="max-w-xl">
            <div className="p-6 sm:p-8">
              <div className="flex items-start justify-between gap-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">FAQ</p>
                  <h2 id="landing-faq-title" className="mt-2 text-2xl font-semibold text-foreground">{faqQuestions[faqIndex]}</h2>
                </div>
                <button type="button" onClick={() => setFaqIndex(null)} className="rounded-xl border border-primary/30 px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent">Close</button>
              </div>
              <p className="mt-5 text-base leading-relaxed text-muted-foreground">{faqAnswers[faqIndex]}</p>
            </div>
          </Modal>
        )}

        {demoOpen && <DemoModal onClose={() => setDemoOpen(false)} />}
        {runItYourselfOpen && <RunItYourselfModal onClose={() => setRunItYourselfOpen(false)} />}
      </div>
    </main>
  );
}

const faqQuestions = [
  'Is PARTHA an AI product?',
  'How do you handle dynamic dispatch, reflection, and generated code?',
  'Which languages are supported?',
  'Where does PARTHA run?',
  'How does PARTHA integrate with our CI?',
  'What is the ri.v1 format?',
] as const;

const faqAnswers = [
  'PARTHA creates deterministic, evidence-backed repository models. AI assistance is optional and is limited to structural facts that have already been computed from a sealed snapshot.',
  'PARTHA makes supported evidence and limits visible. Findings that cannot be verified from the selected revision are not presented as facts.',
  'Language support is determined by the extractors available for the selected repository. The sealed snapshot records exactly what was assessed.',
  'PARTHA analyses a repository at a specific revision and retains a reproducible model for the workspace.',
  'Connect a repository, select a revision, then use the generated evidence and exports in the engineering workflow that suits your team.',
  'ri.v1 is PARTHA’s sealed repository-intelligence snapshot format. It records the exact revision, extracted facts, and available evidence.',
] as const;

type FooterControl = {
  label: string;
  left: string;
  top: string;
  href: string;
  /** true for anything off this site: opens in a new tab with rel=noreferrer.
   * false (or omitted) for same-page anchor scrolls. */
  external?: boolean;
};

const GITHUB_URL = 'https://github.com/Second-Origin/PARTHA';
const REPO_BLOB = `${GITHUB_URL}/blob/dev`;
const DISCORD_URL = 'https://discord.gg/qvk9DcxDA';

// Every hotspot resolves to real, existing content. The four in-page anchors
// scroll the reused artwork; the rest open the maintained doc / repo page that
// actually covers that title. Nothing here is a "coming soon" placeholder.
const footerControls: FooterControl[] = [
  { label: 'How it works', left: '39.1%', top: '93.65%', href: '#how-it-works' },
  { label: 'Capabilities', left: '39.1%', top: '94.45%', href: '#capabilities' },
  { label: 'FAQ', left: '39.1%', top: '95.25%', href: '#faq' },
  { label: 'Privacy', left: '39.1%', top: '96.05%', href: `${REPO_BLOB}/README.md#limitations-and-security`, external: true },
  { label: 'Docs', left: '55%', top: '93.65%', href: `${REPO_BLOB}/docs/README.md`, external: true },
  { label: 'ri.v1 spec', left: '55%', top: '94.45%', href: `${REPO_BLOB}/docs/architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md`, external: true },
  { label: 'Language matrix', left: '55%', top: '95.25%', href: `${REPO_BLOB}/docs/architecture/REPOSITORY_INTELLIGENCE.md#what-is-currently-extracted`, external: true },
  { label: 'Changelog', left: '55%', top: '96.05%', href: `${GITHUB_URL}/releases`, external: true },
  { label: 'About', left: '70.6%', top: '93.65%', href: `${REPO_BLOB}/README.md`, external: true },
  { label: 'Security', left: '70.6%', top: '94.45%', href: `${REPO_BLOB}/SECURITY.md`, external: true },
  { label: 'Contact', left: '70.6%', top: '95.25%', href: DISCORD_URL, external: true },
  { label: 'Legal', left: '70.6%', top: '96.05%', href: `${REPO_BLOB}/LICENSE`, external: true },
  { label: 'LinkedIn', left: '86.3%', top: '93.65%', href: 'https://www.linkedin.com/in/parthrohit', external: true },
  { label: 'X', left: '86.3%', top: '94.45%', href: DISCORD_URL, external: true },
  { label: 'GitHub', left: '86.3%', top: '95.25%', href: GITHUB_URL, external: true },
];

function FooterControl({ item }: { item: FooterControl }) {
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
