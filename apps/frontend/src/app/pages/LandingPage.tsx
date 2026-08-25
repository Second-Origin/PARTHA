import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '@/app/store/useAuthStore';
import { WaitlistModal } from '@/features/waitlist/components/WaitlistModal';
import landingReference from '@/assets/landing/landing-reference.svg';

/**
 * The marketing page is supplied as a complete, authored 1728 × 5608 design
 * canvas. Rendering the source canvas directly avoids scale, font, and layout
 * drift from the signed-off composition. Transparent controls preserve the
 * primary journeys without altering its artwork.
 */
export function LandingPage() {
  const authenticated = useAuthStore((state) => state.status === 'authenticated');
  const [faqIndex, setFaqIndex] = useState<number | null>(null);
  const [footerNotice, setFooterNotice] = useState<string | null>(null);
  const [waitlistOpen, setWaitlistOpen] = useState(false);
  const workspaceHref = authenticated ? '/dashboard' : '/login';

  // Registration is invite-only (#341): an unauthenticated visitor's "analyze
  // a repository" intent opens the waitlist instead of navigating to
  // /register, which they cannot usefully complete without an invite yet.
  const analysisCta = (className: string) =>
    authenticated ? (
      <Link className={className} to="/upload"><span className="sr-only">Analyze a repository</span></Link>
    ) : (
      <button type="button" className={`${className} border-0 bg-transparent p-0`} onClick={() => setWaitlistOpen(true)}>
        <span className="sr-only">Join the waitlist</span>
      </button>
    );

  return (
    <main className="min-h-screen bg-background text-foreground">
      <h1 className="sr-only">Reveal the system behind the code.</h1>
      <div className="relative mx-auto w-full max-w-[1728px]">
        <img
          src={landingReference}
          alt="PARTHA repository intelligence system overview, capabilities, frequently asked questions, and call to action."
          className="block h-auto w-full select-none"
          draggable="false"
        />

        <nav aria-label="PARTHA landing navigation" className="pointer-events-none absolute inset-0 z-20">
          <a className="pointer-events-auto absolute left-[28.5%] top-[0.45%] h-[1.15%] w-[7.5%]" href="#product"><span className="sr-only">Product</span></a>
          <a className="pointer-events-auto absolute left-[37%] top-[0.45%] h-[1.15%] w-[8.5%]" href="#how-it-works"><span className="sr-only">How it works</span></a>
          <a className="pointer-events-auto absolute left-[46.2%] top-[0.45%] h-[1.15%] w-[9.2%]" href="#capabilities"><span className="sr-only">Capabilities</span></a>
          <a className="pointer-events-auto absolute left-[56.5%] top-[0.45%] h-[1.15%] w-[4.5%]" href="#faq"><span className="sr-only">Frequently asked questions</span></a>
          <Link className="pointer-events-auto absolute left-[76%] top-[0.45%] h-[1.15%] w-[5.8%]" to={workspaceHref}><span className="sr-only">{authenticated ? 'Open workspace' : 'Log in'}</span></Link>
          {analysisCta('pointer-events-auto absolute left-[82%] top-[0.35%] h-[1.35%] w-[11%]')}
        </nav>

        <div id="product" className="absolute left-0 top-[18.5%]" />
        <div id="how-it-works" className="absolute left-0 top-[43.9%]" />
        <div id="capabilities" className="absolute left-0 top-[60.5%]" />
        <div id="faq" className="absolute left-0 top-[72.5%]" />

        <a className="absolute left-[28.2%] top-[13.5%] z-20 h-[1.35%] w-[19.1%]" href="#how-it-works"><span className="sr-only">See how PARTHA works</span></a>
        {analysisCta('absolute left-[49.4%] top-[13.5%] z-20 h-[1.35%] w-[22.4%]')}

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

        {analysisCta('absolute left-[36.1%] top-[87.55%] z-20 h-[1.3%] w-[14.8%]')}
        <a className="absolute left-[51%] top-[87.55%] z-20 h-[1.3%] w-[14.8%]" href="https://discord.gg/qvk9DcxDA" target="_blank" rel="noreferrer"><span className="sr-only">Get in touch with PARTHA</span></a>

        <Link className="absolute left-[6.2%] top-[91.9%] z-20 h-[4.3%] w-[22.4%]" to="/" aria-label="PARTHA home" />

        {footerControls.map((item) => (
          <FooterControl key={item.label} item={item} onUnavailable={setFooterNotice} />
        ))}

        {faqIndex !== null && (
          <div role="dialog" aria-modal="true" aria-labelledby="landing-faq-title" className="fixed inset-0 z-50 grid place-items-center bg-foreground/30 p-5">
            <div className="w-full max-w-xl rounded-3xl border border-primary/35 bg-card p-6 shadow-2xl sm:p-8">
              <div className="flex items-start justify-between gap-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">FAQ</p>
                  <h2 id="landing-faq-title" className="mt-2 text-2xl font-semibold text-foreground">{faqQuestions[faqIndex]}</h2>
                </div>
                <button type="button" onClick={() => setFaqIndex(null)} className="rounded-xl border border-primary/30 px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent">Close</button>
              </div>
              <p className="mt-5 text-base leading-relaxed text-muted-foreground">{faqAnswers[faqIndex]}</p>
            </div>
          </div>
        )}

        {waitlistOpen && <WaitlistModal onClose={() => setWaitlistOpen(false)} />}

        {footerNotice && (
          <div role="status" className="fixed bottom-5 left-1/2 z-50 w-[min(92vw,34rem)] -translate-x-1/2 rounded-2xl border border-primary/35 bg-card px-5 py-4 text-center text-sm font-medium text-foreground shadow-xl">
            {footerNotice}
            <button type="button" onClick={() => setFooterNotice(null)} className="ml-3 text-primary underline underline-offset-2">Close</button>
          </div>
        )}
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
  href?: string;
  external?: boolean;
  message?: string;
};

const footerControls: FooterControl[] = [
  { label: 'How it works', left: '39.1%', top: '93.65%', href: '#how-it-works' },
  { label: 'Capabilities', left: '39.1%', top: '94.45%', href: '#capabilities' },
  { label: 'FAQ', left: '39.1%', top: '95.25%', href: '#faq' },
  { label: 'Privacy', left: '39.1%', top: '96.05%', message: 'Privacy details will be published with the public release.' },
  { label: 'Docs', left: '55%', top: '93.65%', href: '/documentation' },
  { label: 'ri.v1 spec', left: '55%', top: '94.45%', message: 'The ri.v1 specification will be available shortly.' },
  { label: 'Language matrix', left: '55%', top: '95.25%', message: 'The language matrix will be available shortly.' },
  { label: 'Changelog', left: '55%', top: '96.05%', message: 'The changelog will be available shortly.' },
  { label: 'About', left: '70.6%', top: '93.65%', message: 'About PARTHA will be available shortly.' },
  { label: 'Security', left: '70.6%', top: '94.45%', message: 'Security details will be available shortly.' },
  { label: 'Contact', left: '70.6%', top: '95.25%', href: 'https://discord.gg/qvk9DcxDA', external: true },
  { label: 'Legal', left: '70.6%', top: '96.05%', message: 'Legal information will be available shortly.' },
  { label: 'LinkedIn', left: '86.3%', top: '93.65%', href: 'https://www.linkedin.com', external: true },
  { label: 'X', left: '86.3%', top: '94.45%', href: 'https://x.com', external: true },
  { label: 'GitHub', left: '86.3%', top: '95.25%', href: 'https://github.com', external: true },
];

function FooterControl({ item, onUnavailable }: { item: FooterControl; onUnavailable: (message: string) => void }) {
  const className = 'absolute z-20 h-[0.9%] w-[10.5%] border-0 bg-transparent p-0';
  const style = { left: item.left, top: item.top };
  if (item.message) {
    return <button type="button" aria-label={item.label} className={className} style={style} onClick={() => onUnavailable(item.message!)} />;
  }
  if (item.external) {
    return <a aria-label={item.label} className={className} style={style} href={item.href} target="_blank" rel="noreferrer" />;
  }
  if (item.href?.startsWith('/')) {
    return <Link aria-label={item.label} className={className} style={style} to={item.href} />;
  }
  return <a aria-label={item.label} className={className} style={style} href={item.href} />;
}
