/* Ported verbatim from the iteration-1 Figma frame
 * (f1HlSxjl8pvvOm86XFPZEJ, "Landing Page" 1:2) via get_design_context.
 *
 * The layout is the design's own absolute geometry inside its native
 * 1728x5608 canvas -- not a re-interpretation. LandingScaler scales the
 * whole canvas to the viewport, so proportions stay exactly as authored.
 * Interactive behaviour is layered on top by the wrappers in App.tsx;
 * nothing here changes the design's own boxes. */

import { createContext, useContext, useEffect, useState, type MouseEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import imgArrow1 from '@/assets/landing/figma/arrow1.png';
import imgArrow2 from '@/assets/landing/figma/arrow2.png';
import imgArrow3 from '@/assets/landing/figma/arrow3.png';
import imgArrow4 from '@/assets/landing/figma/arrow4.png';
import imgCarbonChartRelationship from '@/assets/landing/figma/carbon-chart-relationship.svg';
import imgEllipse14 from '@/assets/landing/figma/ellipse14.svg';
import imgEllipse19 from '@/assets/landing/figma/ellipse19.svg';
import imgEllipse22 from '@/assets/landing/figma/ellipse22.svg';
import imgEllipse23 from '@/assets/landing/figma/ellipse23.svg';
import imgExternalLink from '@/assets/landing/figma/external-link.png';
import imgFrame from '@/assets/landing/figma/frame.svg';
import imgGroup2 from '@/assets/landing/figma/group2.svg';
import imgGroup3 from '@/assets/landing/figma/group3.svg';
import imgGroup4 from '@/assets/landing/figma/group4.svg';
import imgGroup56 from '@/assets/landing/figma/group56.svg';
import imgGroup8 from '@/assets/landing/figma/group8.svg';
import imgIcon2 from '@/assets/landing/figma/icon2.svg';
import imgInspection from '@/assets/landing/figma/inspection.png';
import imgLine5 from '@/assets/landing/figma/line5.svg';
import imgLine6 from '@/assets/landing/figma/line6.svg';
import imgLineMdPlayFilled from '@/assets/landing/figma/line-md-play-filled.svg';
import imgMaskGroup from '@/assets/landing/figma/mask-group.svg';
import imgOcticonRepoForked24 from '@/assets/landing/figma/octicon-repo-forked24.svg';
import imgProductArchitecture from '@/assets/landing/figma/product-architecture.png';
import imgSecuredPackage from '@/assets/landing/figma/secured-package.png';
import imgTablerFilesFilled from '@/assets/landing/figma/tabler-files-filled.svg';
import imgVector10 from '@/assets/landing/figma/vector10.svg';
import imgVector11 from '@/assets/landing/figma/vector11.png';
import imgVector15 from '@/assets/landing/figma/vector15.svg';
import imgVector16 from '@/assets/landing/figma/vector16.svg';
import imgVector17 from '@/assets/landing/figma/vector17.svg';
import imgVector18 from '@/assets/landing/figma/vector18.png';
import imgVector19 from '@/assets/landing/figma/vector19.svg';
import imgVector20 from '@/assets/landing/figma/vector20.svg';
import imgVector21 from '@/assets/landing/figma/vector21.svg';
import imgVector22 from '@/assets/landing/figma/vector22.svg';
import imgVector23 from '@/assets/landing/figma/vector23.svg';
import imgVector24 from '@/assets/landing/figma/vector24.svg';
import imgVector25 from '@/assets/landing/figma/vector25.svg';
import imgVector26 from '@/assets/landing/figma/vector26.svg';
import imgVector27 from '@/assets/landing/figma/vector27.svg';
import imgVector28 from '@/assets/landing/figma/vector28.svg';
import imgVector29 from '@/assets/landing/figma/vector29.svg';
import imgVector3 from '@/assets/landing/figma/vector3.svg';
import imgVector30 from '@/assets/landing/figma/vector30.svg';
import imgVector31 from '@/assets/landing/figma/vector31.svg';
import imgVector32 from '@/assets/landing/figma/vector32.svg';
import imgVector33 from '@/assets/landing/figma/vector33.svg';
import imgVector34 from '@/assets/landing/figma/vector34.svg';
import imgVector35 from '@/assets/landing/figma/vector35.svg';
import imgVector36 from '@/assets/landing/figma/vector36.svg';
import imgVector37 from '@/assets/landing/figma/vector37.svg';
import imgVector38 from '@/assets/landing/figma/vector38.svg';
import imgVector39 from '@/assets/landing/figma/vector39.svg';
import imgVector4 from '@/assets/landing/figma/vector4.png';
import imgVector40 from '@/assets/landing/figma/vector40.svg';
import imgVector41 from '@/assets/landing/figma/vector41.svg';
import imgVector42 from '@/assets/landing/figma/vector42.svg';
import imgVector43 from '@/assets/landing/figma/vector43.svg';
import imgVector44 from '@/assets/landing/figma/vector44.svg';
import imgVector45 from '@/assets/landing/figma/vector45.svg';
import imgVector46 from '@/assets/landing/figma/vector46.svg';
import imgVector47 from '@/assets/landing/figma/vector47.svg';
import imgVector48 from '@/assets/landing/figma/vector48.svg';
import imgVector49 from '@/assets/landing/figma/vector49.svg';
import imgVector5 from '@/assets/landing/figma/vector5.svg';
import imgVector50 from '@/assets/landing/figma/vector50.svg';
import imgVector51 from '@/assets/landing/figma/vector51.svg';
import imgVector52 from '@/assets/landing/figma/vector52.png';
import imgVector6 from '@/assets/landing/figma/vector6.svg';
import imgVector7 from '@/assets/landing/figma/vector7.svg';
import imgVector8 from '@/assets/landing/figma/vector8.svg';
import imgProperty1Default from '@/assets/landing/figma/property1-default.svg';
import imgVector9 from '@/assets/landing/figma/vector9.svg';

import imgCtaArrowDefault from '@/assets/landing/cta-arrow-default.svg';
import imgCtaArrowHover from '@/assets/landing/cta-arrow-hover.svg';
import { cn } from '@/shared/utils/cn';
import imgWordmarkFooterDark from '@/assets/landing/wordmark-vector9-dark.svg';
import imgWordmarkHeaderDark from '@/assets/landing/wordmark-vector50-dark.svg';
import imgBlobInnerDark from '@/assets/landing/blob-vector26-dark.svg';
import imgBlobOuterDark from '@/assets/landing/blob-vector25-dark.svg';
import imgCardShapeDark from '@/assets/landing/card-shape-dark.svg';
import imgParthaMark from '@/assets/landing/figma/vector4.png';
import { CapabilitiesCarousel } from '@/features/landing/components/CapabilitiesCarousel';
import { FaqAccordion } from '@/features/landing/components/FaqAccordion';
import { ThemeControl } from '@/features/landing/components/ThemeControl';
import { StoryCard } from '@/features/landing/components/StoryCard';

/* Where this canvas's controls lead inside the product app.
 *
 * The canvas is the design's own markup; rather than thread routing props
 * through every generated wrapper, the handful of controls that navigate read
 * their destination from here. LandingPage provides the real values, which
 * depend on whether anyone is signed in. */
export type LandingNav = {
  /** "Analyze a Repository" -- registration, or straight to upload when signed in. */
  analyze: string;
  /** Header "Log In" -- the workspace when already signed in. */
  login: string;
  /** Header "Create account". */
  register: string;
  /** "Get in touch with us". */
  contact: string;
  /** Footer "Docs". */
  docs: string;
};

const FALLBACK_NAV: LandingNav = {
  analyze: '/register',
  login: '/login',
  register: '/register',
  contact: '/',
  docs: '/documentation',
};

const LandingNavContext = createContext<LandingNav>(FALLBACK_NAV);

export function LandingNavProvider({ value, children }: { value: LandingNav; children: ReactNode }) {
  return <LandingNavContext.Provider value={value}>{children}</LandingNavContext.Provider>;
}


const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';

function prefersReducedMotion() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia(REDUCED_MOTION).matches;
}

/** How long the word and the spiral mark each hold before trading places. */
const PARTHA_SWAP_MS = 2600;

type ParthaProps = {
  className?: string;
};

/** The "Meet Partha" wordmark (Figma node 562:4198).
 *
 * In the prototype this does not sit still: the word "Partha" and the PARTHA
 * spiral mark trade places, cross-fading one into the other and back for as
 * long as the section is on screen. Timings are measured off the recording --
 * each holds a little under three seconds, with a soft fade between -- and are
 * the two constants below.
 *
 * Under `prefers-reduced-motion` the word simply stays. */
function Partha({ className }: ParthaProps) {
  const [showMark, setShowMark] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia(REDUCED_MOTION);
    const sync = () => setReducedMotion(query.matches);
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    const timer = window.setInterval(() => setShowMark((v) => !v), PARTHA_SWAP_MS);
    return () => window.clearInterval(timer);
  }, [reducedMotion]);

  const swap = reducedMotion ? false : showMark;

  return (
    <div className={className || 'h-[69px] relative w-[184px]'} data-node-id="562:4198">
      <p
        className="[word-break:break-word] absolute font-accent font-medium inset-0 leading-[68.92px] not-italic text-[#ff3c00] text-[78px] text-center tracking-[-4.1352px] whitespace-nowrap transition-opacity duration-[700ms] ease-in-out motion-reduce:transition-none"
        style={{ opacity: swap ? 0 : 1 }}
        data-node-id="562:4196"
      >
        Partha
      </p>
      <img
        alt=""
        aria-hidden
        className="absolute left-1/2 top-1/2 block max-w-none -translate-x-1/2 -translate-y-1/2 transition-opacity duration-[700ms] ease-in-out motion-reduce:transition-none"
        src={imgParthaMark}
        style={{ width: 62, height: 58, opacity: swap ? 1 : 0 }}
      />
    </div>
  );
}

type FooterLinksProps = {
  className?: string;
};

function FooterLinks({ className }: FooterLinksProps) {
  return (
    <div className={className || "h-[211px] relative w-[1020px]"} data-node-id="508:8699">
      <div className="absolute content-stretch flex flex-col gap-[20px] h-[211px] items-start left-[0.16px] top-0 w-[207px]" data-node-id="508:8662" data-name="Container">
        <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="508:8663" data-name="Container">
          <p className="[word-break:break-word] font-display font-medium font-medium leading-[14.286px] relative shrink-0 text-[#7a7a7a] text-[16px] tracking-[1.4px] uppercase whitespace-nowrap" data-node-id="508:8664">
            Product
          </p>
        </div>
        <div className="content-stretch flex flex-col gap-[15px] h-[168px] items-start pt-[12px] relative shrink-0 w-[207px]" data-node-id="508:8665" data-name="List">
          <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="508:8666" data-name="List Item">
            <a href="#how-it-works" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8667">
              How it works
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="508:8668" data-name="List Item">
            <a href="#capabilities" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8669">
              Capabilities
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="508:8670" data-name="List Item">
            <a href="#faq" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8671">
              FAQ
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="508:8672" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/tree/dev/docs" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8673">
              Privacy
            </a>
          </div>
        </div>
      </div>
      <div className="absolute content-stretch flex flex-col gap-[20px] h-[211px] items-start left-[271.16px] top-0 w-[207px]" data-node-id="508:8674" data-name="Container">
        <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="508:8675" data-name="Container">
          <p className="[word-break:break-word] font-display font-medium font-medium leading-[14.286px] relative shrink-0 text-[#7a7a7a] text-[16px] tracking-[1.4px] uppercase whitespace-nowrap" data-node-id="508:8676">
            Resources
          </p>
        </div>
        <div className="content-stretch flex flex-col gap-[15px] h-[149px] items-start pt-[12px] relative shrink-0 w-[207px]" data-node-id="508:8677" data-name="List">
          <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="508:8678" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/tree/dev/docs" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8679">
              Docs
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.336px]" data-node-id="508:8680" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/blob/dev/docs/architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8681">
              ri.v1 spec
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.336px]" data-node-id="508:8682" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/blob/dev/docs/CAPABILITIES.md" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8683">
              Language matrix
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.336px]" data-node-id="508:8684" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/blob/dev/CHANGELOG.md" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8685">
              Changelog
            </a>
          </div>
        </div>
      </div>
      <div className="absolute content-stretch flex flex-col gap-[20px] h-[211px] items-start left-[542px] top-0 w-[207px]" data-node-id="508:8686" data-name="Container">
        <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="508:8687" data-name="Container">
          <p className="[word-break:break-word] font-display font-medium font-medium leading-[14.286px] relative shrink-0 text-[#7a7a7a] text-[16px] tracking-[1.4px] uppercase whitespace-nowrap" data-node-id="508:8688">
            Company
          </p>
        </div>
        <div className="content-stretch flex flex-col gap-[15px] h-[176px] items-start pt-[12px] relative shrink-0 w-[207px]" data-node-id="508:8689" data-name="List">
          <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="508:8690" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/blob/dev/README.md" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8691">
              About
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="508:8692" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/blob/dev/SECURITY.md" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8693">
              Security
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="508:8694" data-name="List Item">
            <a href="https://discord.gg/qvk9DcxDA" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8695">
              Contact
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="508:8696" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA/blob/dev/LICENSE" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="508:8697">
              Legal
            </a>
          </div>
        </div>
      </div>
      <div className="absolute content-stretch flex flex-col gap-[20px] h-[211px] items-start left-[813px] top-0 w-[207px]" data-node-id="548:813" data-name="Container">
        <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="548:814" data-name="Container">
          <p className="[word-break:break-word] font-display font-medium font-medium leading-[14.286px] relative shrink-0 text-[#7a7a7a] text-[16px] tracking-[1.4px] uppercase whitespace-nowrap" data-node-id="548:815">
            Social
          </p>
        </div>
        <div className="content-stretch flex flex-col gap-[15px] h-[176px] items-start pt-[12px] relative shrink-0 w-[207px]" data-node-id="548:816" data-name="List">
          <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="548:817" data-name="List Item">
            <a href="https://www.linkedin.com/in/parthrohit" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="548:818">
              LinkedIn
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="548:819" data-name="List Item">
            <a href="https://discord.gg/qvk9DcxDA" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="548:820">
              Discord
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="548:821" data-name="List Item">
            <a href="https://github.com/Second-Origin/PARTHA" target="_blank" rel="noreferrer" className="[word-break:break-word] font-body font-medium leading-[18.571px] not-italic relative shrink-0 text-[24px] text-[var(--ln-ink-60)] whitespace-nowrap block transition-colors duration-150 hover:text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01]" data-node-id="548:822">
              GitHub
            </a>
          </div>
          <div className="content-stretch flex flex-col h-[27px] items-start pt-[8px] relative shrink-0 w-[207.328px]" data-node-id="548:823" data-name="List Item" />
        </div>
      </div>
    </div>
  );
}

type ButtonV1Props = {
  className?: string;
};

/** The primary CTA, with the two states the design draws for it (Figma
 * "Button v1" 109:33): solid Signal Orange by default, and on hover the fill
 * drops out to white with a 2px orange ring, orange label and the orange
 * arrow. The ring is a shadow rather than a border so the button does not
 * change size between states. */
function ButtonV1({ className }: ButtonV1Props) {
  const nav = useContext(LandingNavContext);
  return (
    <Link to={nav.analyze} className={cn('group block cursor-pointer', className)} data-node-id="109:33">
      <div className="absolute inset-0 rounded-[15px] bg-[#fa4d01] transition-[background-color,box-shadow] duration-200 group-hover:bg-white group-hover:shadow-[0_0_0_2px_#fa4d01] group-focus-visible:bg-white group-focus-visible:shadow-[0_0_0_2px_#fa4d01] motion-reduce:transition-none" />
      <p className="[word-break:break-word] absolute font-display font-semibold inset-[27.94%_24.68%_29.41%_9%] leading-[normal] text-[24px] text-center text-white transition-colors duration-200 whitespace-nowrap group-hover:text-[#fa4d01] group-focus-visible:text-[#fa4d01] motion-reduce:transition-none" data-node-id="109:30">
        Analyze a Repository
      </p>
      <img alt="" className="absolute left-[315px] top-[15px] block h-[38px] w-[43px] max-w-none transition-opacity duration-200 group-hover:opacity-0 group-focus-visible:opacity-0 motion-reduce:transition-none" src={imgCtaArrowDefault} />
      <img alt="" className="absolute left-[319px] top-[13px] block h-[41px] w-[37px] max-w-none opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-visible:opacity-100 motion-reduce:transition-none" src={imgCtaArrowHover} />
    </Link>
  );
}

type LinkV1Props = {
  className?: string;
};

/** The secondary CTA (Figma "Link v1" 116:105). Its hover state fills the
 * outlined button with the design's pale blue tint; border and label do not
 * change. */
function LinkV1({ className }: LinkV1Props) {
  return (
    <a
      href="#how-it-works"
      className={cn(
        'group cursor-pointer bg-white transition-colors duration-200 hover:bg-[var(--ln-tint-blue)] focus-visible:bg-[var(--ln-tint-blue)] motion-reduce:transition-none',
        className,
      )}
      data-node-id="116:105"
    >
      <div className="[word-break:break-word] absolute flex flex-col font-display font-semibold inset-[calc(0%-1px)_calc(6.46%-0.87px)_calc(-0.08%-1px)_-1px] justify-center leading-[0] text-[#006298] text-[24px] text-center" data-node-id="116:102">
        <p className="leading-[normal]">See how it works</p>
      </div>
      <div className="absolute inset-[calc(16.15%-0.68px)_calc(1.79%-0.96px)_calc(17.62%-0.65px)_calc(80.13%+0.6px)]" data-node-id="116:103" data-name="Down" />
      <div className="absolute inset-[calc(16.19%-0.68px)_calc(3.97%-0.92px)_calc(17.58%-0.65px)_calc(82.31%+0.65px)]" data-node-id="571:7279" data-name="line-md:play-filled">
        <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgLineMdPlayFilled} />
      </div>
    </a>
  );
}

export function LandingCanvas() {
  const nav = useContext(LandingNavContext);

  const handleBackToTop = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="landing-canvas bg-[var(--ln-page)] relative size-full" data-node-id="1:2" data-name="Landing Page">
      <div className="absolute h-[873px] left-0 overflow-clip top-[133px] w-[1728px]" data-node-id="143:163" data-name="Container - Hero">
        <div className="absolute h-[841px] left-[1128px] top-[-142px] w-[1014px]" data-node-id="573:7511">
          <div className="absolute inset-[-11.89%_-9.86%]">
            <img alt="" className="block max-w-none size-full" src={imgEllipse23} />
          </div>
        </div>
        <div className="absolute h-[749px] left-[-383px] top-[96px] w-[766px]" data-node-id="573:7508">
          <div className="absolute inset-[-13.35%_-13.05%]">
            <img alt="" className="block max-w-none size-full" src={imgEllipse22} />
          </div>
        </div>
        <p className="-translate-x-1/2 [word-break:break-word] absolute capitalize font-display font-extrabold font-extrabold h-[321px] leading-[normal] left-[867px] text-[var(--ln-hero-head)] text-[92px] text-center top-[144px] w-[914px] whitespace-pre-wrap" data-node-id="97:171">
          {`Reveal the system `}
          <br aria-hidden />
          behind the code.
        </p>
        <div className="-translate-x-1/2 [word-break:break-word] absolute font-accent font-normal h-[132px] leading-[0] left-[866.5px] not-italic text-[32px] text-[var(--ln-ink)] text-center top-[482px] w-[863px]" data-node-id="97:230">
          <p className="leading-[normal] mb-0">PARTHA analyzes a Git repository at a specific revision and produces a sealed, evidence-backed model of the system. Deterministic. Reproducible. Honest about its limits.</p>
          <p className="leading-[normal]">&#8203;</p>
        </div>
        <div className="[word-break:break-word] absolute font-body font-normal h-[27px] leading-[0] left-[467px] not-italic text-[#7a7a7a] text-[20px] text-justify top-[733px] uppercase w-[857px]" data-node-id="102:13">
          <p className="leading-[normal] mb-0">Connect a repository. PARTHA maps the system. You verify the evidence.</p>
          <p className="leading-[normal]">&#8203;</p>
        </div>
        <div className="absolute content-stretch flex gap-[44px] items-center left-[490px] top-[631px]" data-node-id="573:7513">
          <LinkV1 className="border border-[#006298] border-solid h-[67.944px] relative rounded-[15px] shrink-0 w-[320.735px]" />
          <ButtonV1 className="h-[68px] relative rounded-[34px] shrink-0 w-[389px]" />
        </div>
        <div className="absolute h-[28px] left-[717px] top-[82px] w-[299px]" data-node-id="571:7331" data-name="eyebrow">
          <div className="absolute bg-[rgba(250,77,1,0.05)] border border-[#fa4d01] border-solid inset-0 rounded-[30px]" data-node-id="571:7332" />
          <p className="[word-break:break-word] absolute font-display font-light font-light inset-[17.86%_3.68%_21.43%_9.36%] leading-[normal] text-[14px] text-[var(--ln-ink)] text-justify uppercase" data-node-id="571:7333">
            Repository Intelligence System
          </p>
          <div className="absolute inset-[32.14%_93.65%_32.14%_3.01%]" data-node-id="571:7334">
            <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgEllipse14} />
          </div>
        </div>
        <div className="absolute inset-[13.45%_4.92%_77.54%_90.22%] opacity-40 overflow-clip" data-node-id="576:7523" data-name="PARTHA-logo-FA4D01-transparent 3 1">
          <div className="absolute contents inset-0" data-node-id="576:7524" data-name="Clip path group">
            <div className="absolute contents inset-0" data-node-id="576:7527" data-name="Group">
              <div className="absolute inset-0 mask-alpha mask-intersect mask-no-clip mask-no-repeat mask-size-[84px_78.607px]" data-node-id="576:7528" style={{ maskImage: `url("${imgVector3}")` }} data-name="Vector">
                <img alt="" className="absolute block inset-0 max-w-none size-full" height="78.607" src={imgVector4} width="84" />
              </div>
            </div>
          </div>
        </div>
        <div className="absolute inset-[37.82%_14.53%_56.67%_83.39%]" data-node-id="576:7533" data-name="Vector">
          <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector5} />
        </div>
        <div className="absolute flex inset-[23.2%_7.12%_58.69%_85.65%] items-center justify-center" data-node-id="576:7535" style={{ containerType: "size" }}>
          <div className="-rotate-90 flex-none h-[100cqw] w-[100cqh]">
            <div className="relative size-full" data-name="Vector">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector6} />
            </div>
          </div>
        </div>
        <div className="absolute inset-[36.55%_80.03%_38.35%_2.43%]" data-node-id="577:7750" data-name="Vector">
          <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector7} />
        </div>
        <div className="absolute flex inset-[51.38%_80.32%_6.25%_8.16%] items-center justify-center" data-node-id="577:7752" style={{ containerType: "size" }}>
          <div className="flex-none h-[100cqw] rotate-90 w-[100cqh]">
            <div className="relative size-full" data-name="Vector">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector8} />
            </div>
          </div>
        </div>
      </div>
      <div className="absolute bg-[var(--ln-page)] h-[885px] left-0 top-[2461px] w-[1734px]" data-node-id="436:5657" />
      <div className="absolute h-[252px] left-[80px] right-[1213px] top-[4189px]" data-node-id="480:7839" data-name="Container">
        <div className="absolute content-stretch flex h-[36px] items-center left-0 right-0 top-[-19px]" data-node-id="480:7840" data-name="Container">
          <div className="[word-break:break-word] capitalize flex flex-col font-display font-extralight font-extralight h-[36px] justify-center leading-[0] relative shrink-0 text-[32px] text-[var(--ln-ink)] tracking-[1.32px] w-[71px]" data-node-id="480:7841">
            <p className="leading-[16.5px] whitespace-nowrap">FAQ</p>
          </div>
        </div>
        <div className="absolute h-[252px] left-0 top-[17px] w-[1036px]" data-node-id="480:7842" data-name="Heading 2">
          <p className="[word-break:break-word] absolute font-display font-normal font-normal leading-[54px] left-0 text-[48px] text-[var(--ln-ink)] top-[12px] tracking-[-2.88px] w-[410px]" data-node-id="480:7843">
            Questions Engineers actually ask
          </p>
        </div>
      </div>
      <FaqAccordion id="faq" className="absolute border border-[rgba(250,77,1,0.3)] border-solid left-[539px] overflow-hidden rounded-[12px] top-[4201px] w-[1109px]" />
      <div className="absolute bg-[var(--ln-cta)] border border-[#fa4d01] border-solid h-[405px] left-[141px] overflow-clip rounded-[30px] shadow-[4px_4px_4px_0px_rgba(250,77,1,0.25)] top-[4638px] w-[1437px]" data-node-id="504:8541" data-name="contact">
        <p className="-translate-x-1/2 [word-break:break-word] absolute font-display font-light font-light leading-[48px] left-[717.5px] text-[48px] text-[var(--ln-ink)] text-center top-[68px] tracking-[-1.2px] w-[761px]" data-node-id="504:8522">
          Understand the system behind the code.
        </p>
        <p className="-translate-x-1/2 [word-break:break-word] absolute font-accent font-normal leading-[24px] left-[717.5px] not-italic text-[20px] text-[var(--ln-ink)] text-center top-[192px] w-[697px]" data-node-id="504:8542">{`PARTHA is currently in private preview with a small group of engineering teams. Request access and we'll follow up with onboarding materials and a self-hosted install guide.`}</p>
        <div className="-translate-x-1/2 absolute content-stretch flex gap-[26px] items-center left-1/2 px-[256px] top-[292px]" data-node-id="504:8527" data-name="Container">
          <Link to={nav.analyze} className="h-[43px] relative rounded-[34px] shrink-0 w-[245px] cursor-pointer block" data-node-id="504:8555" data-name="Button v1">
            <div className="absolute bg-[#fa4d01] inset-0 rounded-[15px]" data-node-id="504:8556" />
            <p className="[word-break:break-word] absolute font-display font-semibold font-semibold inset-[27.94%_22.84%_25.55%_6.96%] leading-[normal] text-[16px] text-center text-white whitespace-nowrap" data-node-id="504:8557">
              Analyze a Repository
            </p>
            <div className="absolute inset-[22.06%_7.97%_22.06%_80.98%]" data-node-id="504:8558" data-name="External Link">
              <img alt="" className="absolute inset-0 max-w-none object-contain pointer-events-none size-full" src={imgExternalLink} />
            </div>
          </Link>
          <a href={nav.contact} target="_blank" rel="noreferrer" className="bg-[#f8fafd] border border-[#fa4d01] border-solid h-[43px] relative rounded-[15px] shrink-0 w-[198px] cursor-pointer block" data-node-id="504:8534" data-name="Link">
            <p className="[word-break:break-word] absolute font-display font-medium font-medium leading-[20px] left-[16px] text-[#fa4d01] text-[16px] top-[11px] whitespace-nowrap" data-node-id="504:8535">
              Get in touch with us
            </p>
          </a>
        </div>
      </div>
      <div className="absolute bg-[var(--ln-bar)] h-[483px] left-0 top-[5125px] w-[1728px]" data-node-id="504:8559" data-name="Container (PARTHA — Understand the system behind the code)">
        <button className="absolute block cursor-pointer h-[148px] left-[167px] right-[1159px] top-[104px]" data-node-id="504:8560" data-name="Container">
          <div className="absolute h-[130.281px] left-0 top-[14px] w-[402px]" data-node-id="504:8561" data-name="Container">
            <div className="absolute h-[20px] left-0 right-0 top-0" data-node-id="504:8562" data-name="Container">
              <a href="#top" aria-label="PARTHA, back to top" onClick={handleBackToTop} className="absolute h-[89px] left-0 overflow-clip top-0 w-[322px] block cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01]" data-node-id="506:8651" data-name="LOGO">
                <div className="absolute inset-[29.21%_3.11%_4.49%_25.78%]" data-node-id="506:8652" data-name="Vector">
                  <img alt="" className="wordmark-light absolute block inset-0 max-w-none size-full" src={imgVector9} />
                  <img alt="" className="wordmark-dark absolute block inset-0 max-w-none size-full" src={imgWordmarkFooterDark} />
                </div>
                <div className="absolute contents inset-[18.52%_77.33%_-5.62%_0]" data-node-id="506:8653" data-name="Clip path group">
                  <div className="absolute contents inset-[18.52%_78.33%_3.41%_0]" data-node-id="506:8656" data-name="Group">
                    <div className="absolute inset-[18.52%_78.33%_3.41%_0] mask-alpha mask-intersect mask-no-clip mask-no-repeat mask-size-[73px_77.519px]" data-node-id="506:8657" style={{ maskImage: `url("${imgVector10}")` }} data-name="Vector">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" height="69.482" src={imgVector11} width="69.779" />
                    </div>
                  </div>
                </div>
              </a>
            </div>
            <p className="[word-break:break-word] absolute font-accent font-normal leading-[16px] left-[83px] not-italic text-[#7a7a7a] text-[15px] text-left top-[94px] w-[310px]" data-node-id="508:8659">
              Deterministic repository intelligence. Sealed, evidence-backed models of the system behind the code.
            </p>
          </div>
        </button>
        <div className="absolute h-[82px] left-[24px] right-[24px] top-[333px]" data-node-id="504:8650" data-name="Container:margin" />
        <div className="absolute border-[rgba(250,77,1,0.2)] border-solid border-t h-[42px] left-[24px] top-[373px] w-[1680px]" data-node-id="504:8638" data-name="Container">
          <p className="[word-break:break-word] absolute font-accent font-semibold leading-[16.5px] left-[711px] not-italic text-[15px] text-[var(--ln-ink-60)] top-[20px] whitespace-nowrap" data-node-id="504:8640">
            All rights reserved. Copyright © 2026 Partha
          </p>
        </div>
        <ThemeControl className="absolute h-[38px] left-[1429px] top-[394px] w-[131px]" />
        <FooterLinks className="absolute h-[211px] left-[679px] top-[104px] w-[750px]" />
      </div>
      <div className="absolute h-[797px] left-[74px] top-[2461px] w-[1583px]" id="how-it-works" data-node-id="539:4780" data-name="how it works">
        <div className="absolute content-stretch flex flex-col items-center left-[662px] top-[40px]" data-node-id="539:4781" data-name="Heading 2">
          <p className="[word-break:break-word] font-display font-extralight font-extralight leading-[48px] relative shrink-0 text-[32px] text-[var(--ln-ink)] text-center tracking-[-2.88px] whitespace-nowrap" data-node-id="539:4782">
            How Partha Works
          </p>
        </div>
        <div className="absolute h-[48px] left-[574px] top-[88px] w-[423px]" data-node-id="539:4898" data-name="Heading 3">
          <p className="-translate-x-1/2 [word-break:break-word] absolute font-display font-normal font-normal leading-[48px] left-[211.5px] text-[48px] text-[var(--ln-ink)] text-center top-0 tracking-[-2.88px] whitespace-nowrap" data-node-id="539:4899">
            From code to clarity
          </p>
        </div>
        <div className="absolute h-[604px] left-0 top-[166px] w-[1583px]" data-node-id="539:4783" data-name="Container">
          <div className="absolute bg-[var(--ln-blue)] content-stretch flex flex-col h-[604px] items-center left-0 overflow-clip p-[24px] rounded-[20px] top-0 w-[382px]" data-node-id="539:4784" data-name="Container">
            <div className="content-stretch flex flex-col h-[98px] items-start mb-[-24px] relative shrink-0 w-[272px]" data-node-id="539:4785" data-name="Container">
              <div className="content-stretch flex flex-[98_0_0] flex-col gap-[16px] items-start min-h-px relative" data-node-id="539:4786" data-name="Container">
                <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4787" data-name="Paragraph">
                  <p className="[word-break:break-word] capitalize font-display font-normal font-normal leading-[18px] relative shrink-0 text-[18px] text-[var(--ln-ink)] tracking-[-0.72px] whitespace-nowrap" data-node-id="539:4788">
                    import repository
                  </p>
                </div>
                <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4789" data-name="Paragraph">
                  <p className="[word-break:break-word] capitalize font-accent font-normal leading-[32px] not-italic relative shrink-0 text-[32px] text-[var(--ln-ink)] tracking-[-1.28px] whitespace-nowrap" data-node-id="539:4790">{`select your source `}</p>
                </div>
              </div>
            </div>
            <div className="content-stretch flex h-[417px] items-center justify-center mb-[-24px] relative shrink-0 w-[272px]" data-node-id="539:4791" data-name="Container">
              <div className="h-[243px] max-w-[290px] relative shrink-0 w-[272px]" data-node-id="539:4792" data-name="Container">
                <div className="absolute border-[#fa4d01] border-[1.5px] border-dashed h-[253px] left-[20px] rounded-[125px] top-[0.43px] w-[250px]" data-node-id="539:4793" data-name="Container" />
                <div className="absolute bg-[var(--extended-colors\/on-custom-color-1,white)] border border-[#fa4d01] border-solid content-stretch flex h-[41px] items-center left-[73px] px-[10px] py-[8px] rounded-[7px] top-[-7px] w-[63px]" data-node-id="539:4794" data-name="Container">
                  <p className="[word-break:break-word] font-body font-normal leading-[normal] not-italic relative shrink-0 text-[var(--ln-ink)] text-[10.4px] tracking-[-0.312px] whitespace-nowrap" data-node-id="539:4795">
                    Revision
                  </p>
                </div>
                <div className="absolute bg-[#fa4d01] content-stretch flex gap-[4px] h-[38px] items-center justify-center left-[162px] px-[12px] rounded-[7px] top-[108px] w-[119px]" data-node-id="539:4796" data-name="Container">
                  <div className="overflow-clip relative shrink-0 size-[16px]" data-node-id="539:4797" data-name="Icon">
                    <div className="absolute left-[1.5px] size-[14px] top-px" data-node-id="539:4798" data-name="Secured Package">
                      <img alt="" className="absolute inset-0 max-w-none object-contain pointer-events-none size-full" src={imgSecuredPackage} />
                    </div>
                  </div>
                  <p className="[word-break:break-word] font-body font-normal leading-[normal] not-italic relative shrink-0 text-[10.4px] text-[color:var(--extended-colors\/on-custom-color-1,white)] tracking-[-0.312px] whitespace-nowrap" data-node-id="539:4799">
                    Sealed Snapshot
                  </p>
                </div>
                <div className="absolute bg-[var(--extended-colors\/on-custom-color-1,white)] border border-[#fa4d01] border-solid content-stretch flex gap-[4px] h-[41px] items-center justify-center left-[10px] px-[8px] rounded-[6px] top-[202px] w-[88px]" data-node-id="539:4800" data-name="Container">
                  <div className="overflow-clip relative shrink-0 size-[16px]" data-node-id="539:4801" data-name="Icon">
                    <div className="absolute left-px size-[14px] top-[1.07px]" data-node-id="539:4802" data-name="octicon:repo-forked-24">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgOcticonRepoForked24} />
                    </div>
                  </div>
                  <p className="[word-break:break-word] font-body font-normal leading-[normal] not-italic relative shrink-0 text-[var(--ln-ink)] text-[10.4px] tracking-[-0.312px] whitespace-nowrap" data-node-id="539:4806">
                    Repository
                  </p>
                </div>
              </div>
            </div>
            <p className="[word-break:break-word] font-body font-normal leading-[21.125px] not-italic relative shrink-0 text-[16px] text-[var(--ln-ink)] w-[272px]" data-node-id="539:4807">{`Connect a repository, choose the revision you want to analyze, & let PARTHA create a sealed snapshot tied to that exact version.`}</p>
          </div>
          <div className="absolute bg-[var(--ln-grey)] content-stretch flex flex-col h-[604px] items-center left-[400px] overflow-clip p-[24px] rounded-[20px] top-0 w-[382px]" data-node-id="539:4808" data-name="Container">
            <div className="content-stretch flex flex-col gap-[16px] items-start mb-[-10px] relative shrink-0 w-[272px]" data-node-id="539:4809" data-name="Container">
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4810" data-name="Paragraph">
                <p className="[word-break:break-word] capitalize font-display font-normal font-normal leading-[18px] relative shrink-0 text-[18px] text-[var(--ln-ink)] tracking-[-0.72px] whitespace-nowrap" data-node-id="539:4811">
                  PARTHA analyzes
                </p>
              </div>
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4812" data-name="Paragraph">
                <p className="[word-break:break-word] capitalize font-accent font-normal leading-[32px] not-italic relative shrink-0 text-[32px] text-[var(--ln-ink)] tracking-[-1.28px] w-[272px]" data-node-id="539:4813">{`we extract, map, & connect`}</p>
              </div>
            </div>
            <div className="h-[364px] mb-[-10px] relative shrink-0 w-[272px]" data-node-id="539:4814" data-name="Container">
              <div className="absolute h-[213px] left-0 overflow-clip top-[75px] w-[140px]" data-node-id="539:4815" data-name="Icon">
                <div className="absolute inset-[0.35%_0.54%]" data-node-id="539:4816" data-name="Vector">
                  <div className="absolute inset-[-0.27%_-0.49%_-0.33%_-0.54%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector15} />
                  </div>
                </div>
                <div className="absolute inset-[5.87%_8.57%]" data-node-id="539:4817" data-name="Vector">
                  <div className="absolute inset-[-0.27%_-0.43%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector16} />
                  </div>
                </div>
                <div className="absolute inset-[5.87%_8.57%]" data-node-id="539:4818" data-name="Mask group">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgMaskGroup} />
                </div>
                <div className="[word-break:break-word] absolute contents font-body font-normal italic inset-[10.7%_22.5%_14.18%_22.5%] italic leading-[normal] text-[11.7px] text-[var(--ln-ink)] text-center whitespace-nowrap" data-node-id="539:4822" data-name="Group">
                  <p className="absolute inset-[10.7%_41.07%_81.78%_41.07%]" data-node-id="539:4823">
                    Files
                  </p>
                  <p className="absolute inset-[33.24%_33.21%_59.25%_33.21%]" data-node-id="539:4824">
                    Symbols
                  </p>
                  <p className="absolute inset-[55.77%_22.5%_36.71%_22.5%]" data-node-id="539:4825">
                    Dependencies
                  </p>
                  <p className="absolute inset-[78.31%_22.86%_14.18%_23.57%]" data-node-id="539:4826">
                    Relationships
                  </p>
                </div>
              </div>
              <div className="absolute bg-white left-[222px] rounded-[10px] size-[50px] top-[157px]" data-node-id="539:4827" />
              <div className="absolute inset-[44.51%_1.84%_44.51%_83.46%] overflow-clip" data-node-id="539:4828" data-name="PARTHA-logo-FA4D01-transparent 3 1">
                <div className="absolute contents inset-0" data-node-id="539:4829" data-name="Clip path group">
                  <div className="absolute contents inset-0" data-node-id="539:4832" data-name="Group">
                    <div className="absolute inset-0 mask-alpha mask-intersect mask-no-clip mask-no-repeat mask-size-[40px_40px]" data-node-id="539:4833" style={{ maskImage: `url("${imgVector17}")` }} data-name="Vector">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" height="40" src={imgVector18} width="40" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute flex h-[74.328px] items-center justify-center left-[137.14px] top-[88px] w-[96.856px]" data-node-id="539:4834">
                <div className="flex-none rotate-[21.48deg] skew-x-[1.32deg]">
                  <div className="h-[45.09px] relative w-[87.389px]">
                    <div className="absolute inset-[-0.98%_0_-5.89%_-0.79%]">
                      <img alt="" className="block max-w-none size-full" height="48.189" src={imgArrow1} width="88.084" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute flex h-[74.519px] items-center justify-center left-[136px] top-[200px] w-[97.351px]" data-node-id="539:4835">
                <div className="-scale-y-100 flex-none rotate-[-21.48deg] skew-x-[-1.32deg]">
                  <div className="h-[45.085px] relative w-[87.923px]">
                    <div className="absolute inset-[-0.99%_0_-5.88%_-0.79%]">
                      <img alt="" className="block max-w-none size-full" height="48.185" src={imgArrow4} width="88.617" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute flex h-[19.577px] items-center justify-center left-[142.76px] top-[152.93px] w-[73.38px]" data-node-id="539:4836">
                <div className="flex-none rotate-[12.79deg] skew-x-[0.83deg]">
                  <div className="h-[3.14px] relative w-[74.579px]">
                    <div className="absolute inset-[-15.93%_0_-69.99%_-0.76%]">
                      <img alt="" className="block max-w-none size-full" height="5.837" src={imgArrow2} width="75.142" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute flex h-[19.577px] items-center justify-center left-[142.76px] top-[190px] w-[73.38px]" data-node-id="539:4837">
                <div className="-scale-y-100 flex-none rotate-[-12.79deg] skew-x-[-0.83deg]">
                  <div className="h-[3.14px] relative w-[74.579px]">
                    <div className="absolute inset-[-15.93%_0_-69.99%_-0.76%]">
                      <img alt="" className="block max-w-none size-full" height="5.837" src={imgArrow3} width="75.142" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <p className="[word-break:break-word] font-body font-normal leading-[21.125px] not-italic relative shrink-0 text-[16px] text-[var(--ln-ink)] w-[272px]" data-node-id="539:4838">{`PARTHA maps the repository’s files, symbols, routes, dependencies, & relationships while generating evidence for the supported parts of the system.`}</p>
          </div>
          <div className="absolute bg-[var(--ln-sand)] content-stretch flex flex-col h-[604px] items-center left-[800px] overflow-clip p-[24px] rounded-[20px] top-0 w-[382px]" data-node-id="539:4839" data-name="Container">
            <div className="content-stretch flex flex-col gap-[16px] items-start mb-[-16px] relative shrink-0 w-[272px]" data-node-id="539:4840" data-name="Container">
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4841" data-name="Paragraph">
                <p className="[word-break:break-word] capitalize font-display font-normal font-normal leading-[18px] relative shrink-0 text-[18px] text-[var(--ln-ink)] tracking-[-0.72px] whitespace-nowrap" data-node-id="539:4842">{`explore & verify`}</p>
              </div>
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4843" data-name="Paragraph">
                <p className="[word-break:break-word] capitalize font-accent font-normal leading-[32px] not-italic relative shrink-0 text-[32px] text-[var(--ln-ink)] tracking-[-1.28px] w-[272px]" data-node-id="539:4844">
                  navigate the system with evidence
                </p>
              </div>
            </div>
            <div className="content-stretch flex h-[392px] items-center justify-center mb-[-16px] relative shrink-0 w-[272px]" data-node-id="539:4845" data-name="Container">
              <div className="h-[204.375px] overflow-clip relative shrink-0 w-[272px]" data-node-id="539:4846" data-name="Icon">
                <div className="absolute inset-[0.09%_0_68.59%_64.34%]" data-node-id="539:4847" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector19} />
                </div>
                <div className="absolute inset-[21.62%_74.34%_58.9%_11.03%]" data-node-id="539:4848" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector20} />
                </div>
                <div className="absolute inset-[72.79%_19.9%_7.73%_65.47%]" data-node-id="539:4849" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector21} />
                </div>
                <div className="absolute inset-[19.17%_37.5%_66.15%_47.79%]" data-node-id="539:4850" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector22} />
                </div>
                <div className="absolute inset-[67.14%_35.8%_16.03%_54.59%]" data-node-id="539:4851" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector23} />
                </div>
                <div className="absolute inset-[42.5%_61.77%_49.49%_17.85%]" data-node-id="539:4852" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector24} />
                </div>
                <div className="absolute contents inset-[35.29%_38.76%_35.04%_38.95%]" data-node-id="539:4853" data-name="Mask group">
                  <div className="absolute inset-[35.29%_38.76%_35.04%_38.95%] mask-intersect mask-luminance mask-no-clip mask-no-repeat mask-size-[60.639px_60.639px]" data-node-id="539:4856" style={{ maskImage: `url("${imgGroup2}")` }} data-name="Group">
                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgGroup3} />
                  </div>
                  <div className="absolute inset-[40.21%_42.65%] mask-intersect mask-luminance mask-no-clip mask-no-repeat mask-position-[-10.055px_-10.055px] mask-size-[60.639px_60.639px] overflow-clip" data-node-id="539:4858" style={{ maskImage: `url("${imgGroup2}")` }} data-name="PARTHA-logo-FA4D01-transparent 3 1">
                    <div className="absolute contents inset-0" data-node-id="539:4859" data-name="Clip path group">
                      <div className="absolute contents inset-0" data-node-id="539:4862" data-name="Group">
                        <div className="absolute inset-0 mask-alpha mask-intersect mask-no-clip mask-no-repeat mask-size-[40px_40px]" data-node-id="539:4863" style={{ maskImage: `url("${imgVector17}")` }} data-name="Vector">
                          <img alt="" className="absolute block inset-0 max-w-none size-full" height="40" src={imgVector18} width="40" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="absolute inset-[27.45%_78.33%_64.72%_15.05%]" data-node-id="539:4864" data-name="Product Architecture">
                  <img alt="" className="absolute inset-0 max-w-none object-contain pointer-events-none size-full" src={imgProductArchitecture} />
                </div>
                <p className="[word-break:break-word] absolute font-body font-normal inset-[8.41%_4.78%_85.23%_73.53%] leading-[13px] not-italic text-[10px] text-[var(--ln-ink)] tracking-[-0.9px] whitespace-nowrap" data-node-id="539:4865">
                  auth.service.ts
                </p>
                <p className="[word-break:break-word] absolute font-body font-normal inset-[19.17%_9.19%_74.46%_73.53%] leading-[13px] not-italic text-[10px] text-[var(--ln-ink)] tracking-[-0.9px] whitespace-nowrap" data-node-id="539:4866">
                  Lines 42–78
                </p>
                <div className="absolute left-[182px] overflow-clip size-[14px] top-[16.19px]" data-node-id="539:4867" data-name="gala:file">
                  <div className="absolute inset-[6.25%_12.5%]" data-node-id="539:4868" data-name="Group">
                    <div className="absolute inset-[-4.08%_-4.76%]">
                      <img alt="" className="block max-w-none size-full" src={imgGroup4} />
                    </div>
                  </div>
                </div>
                <div className="absolute h-[16px] left-[189px] overflow-clip top-[160.19px] w-[18px]" data-node-id="539:4880" data-name="Icon">
                  <div className="absolute h-[16px] left-0 top-0 w-[18px]" data-node-id="539:4881" data-name="Inspection">
                    <div aria-hidden className="absolute inset-0 pointer-events-none">
                      <img alt="" className="absolute max-w-none object-contain size-full" src={imgInspection} />
                      <img alt="" className="absolute max-w-none object-contain size-full" src={imgInspection} />
                      <img alt="" className="absolute max-w-none object-contain size-full" src={imgInspection} />
                      <img alt="" className="absolute max-w-none object-contain size-full" src={imgInspection} />
                      <img alt="" className="absolute max-w-none object-contain size-full" src={imgInspection} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <p className="[word-break:break-word] font-body font-normal leading-[17.6px] not-italic relative shrink-0 text-[16px] text-[var(--ln-ink)] tracking-[-0.32px] w-[272px]" data-node-id="539:4882">
              Explore the architecture and relationships, then trace supported findings back to the exact file, symbol, line range, and revision that produced them.
            </p>
          </div>
          <div className="absolute bg-[var(--ln-orange)] content-stretch flex flex-col h-[604px] items-center left-[1200px] overflow-clip p-[24px] rounded-[20px] top-0 w-[382px]" data-node-id="539:4883" data-name="Container">
            <div className="content-stretch flex flex-col gap-[16px] items-start mb-[-16px] relative shrink-0 w-[272px]" data-node-id="539:4884" data-name="Container">
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4885" data-name="Paragraph">
                <p className="[word-break:break-word] capitalize font-display font-normal font-normal leading-[18px] relative shrink-0 text-[18px] text-[var(--ln-ink)] tracking-[-0.72px] whitespace-nowrap" data-node-id="539:4886">{`review & act`}</p>
              </div>
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="539:4887" data-name="Paragraph">
                <p className="[word-break:break-word] capitalize font-accent font-normal leading-[32px] not-italic relative shrink-0 text-[32px] text-[var(--ln-ink)] tracking-[-1.28px] w-[272px]" data-node-id="539:4888">
                  make confident engineering decisions
                </p>
              </div>
            </div>
            <div className="content-stretch flex h-[379px] items-center justify-center mb-[-16px] relative shrink-0 w-[272px]" data-node-id="539:4889" data-name="Container">
              <div className="h-[148px] relative shrink-0 w-[117px]" data-node-id="539:4890" data-name="Icon">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIcon2} />
              </div>
            </div>
            <div className="content-stretch flex flex-col items-start relative shrink-0 w-[272px]" data-node-id="539:4895" data-name="Paragraph">
              <p className="[word-break:break-word] font-body font-normal leading-[17.6px] not-italic relative shrink-0 text-[16px] text-[var(--ln-ink)] tracking-[-0.32px] w-[272px]" data-node-id="539:4896">{`Use evidence-backed findings, insights, documentation, & exports to understand the system & make engineering decisions with clear visibility into what was & was not assessed.`}</p>
            </div>
          </div>
        </div>
      </div>
      <div className="absolute contents left-[169px] top-[3413px]" data-node-id="573:7522">
        <div className="absolute contents left-[169px] top-[3491px]" data-node-id="573:7518">
          <CapabilitiesCarousel id="capabilities" className="absolute h-[518px] left-[169px] top-[3491px] w-[1390px]" />
          <div className="absolute flex items-center justify-center left-[1166px] size-[115px] top-[3618px]" data-node-id="534:4547">
            <div className="-rotate-90 flex-none">
              <div className="relative size-[115px]" data-name="Frame">
                <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgFrame} />
              </div>
            </div>
          </div>
        </div>
        <div className="absolute content-stretch flex flex-col items-center left-[677px] top-[3413px]" data-node-id="573:7519" data-name="Heading 4">
          <p className="[word-break:break-word] font-display font-extralight font-extralight leading-[48px] relative shrink-0 text-[32px] text-[var(--ln-ink)] text-center tracking-[-2.88px] whitespace-nowrap" data-node-id="573:7520">
            What Is PARTHA Capable Of
          </p>
        </div>
      </div>
      <div className="absolute h-[1384px] left-[74px] top-[1006px] w-[1583px]" data-node-id="550:1349" data-name="product">
        <div className="absolute h-[1328px] left-[-16px] right-[-16px] top-0" data-node-id="550:1350" data-name="Container">
          <div id="product" className="absolute content-stretch flex flex-col gap-[16px] items-center left-[515px] top-[107px]" data-node-id="550:1351" data-name="Container">
            <div className="content-stretch flex gap-[10px] items-center justify-center px-[97px] relative shrink-0" data-node-id="562:4194" data-name="Meet Partha">
              <p className="[word-break:break-word] font-body font-normal leading-[68.92px] not-italic relative shrink-0 text-[68.92px] text-[var(--ln-ink)] text-center tracking-[-4.1352px] whitespace-nowrap" data-node-id="562:4195">{`Meet `}</p>
              <Partha className="h-[69px] relative shrink-0 w-[184px]" />
            </div>
            <div className="content-stretch flex flex-col items-center relative shrink-0" data-node-id="550:1354" data-name="Paragraph">
              <p className="[word-break:break-word] font-accent font-normal leading-[23.24px] not-italic relative shrink-0 text-[#7a7a7a] text-[36px] text-center tracking-[-1.12px] w-[351px]" data-node-id="550:1355">
                Understand your codebase
              </p>
            </div>
          </div>
          <div className="absolute inset-[19.87%_1.99%_1.38%_1.99%]" data-node-id="552:1641" data-name="Vector">
            <img alt="" className="theme-light-art absolute block inset-0 max-w-none size-full" src={imgVector25} />
              <img alt="" className="theme-dark-art absolute block inset-0 max-w-none size-full" src={imgBlobOuterDark} />
          </div>
          <StoryCard className="absolute h-[499px] left-[32px] top-[264px] w-[751px]" />
          <div className="absolute contents left-[62.15px] top-[298px]" data-node-id="562:3932">
            <div className="absolute inset-[22.44%_3.85%_3.99%_3.85%]" data-node-id="560:3744" data-name="Vector">
              <img alt="" className="theme-light-art absolute block inset-0 max-w-none size-full" src={imgVector26} />
              <img alt="" className="theme-dark-art absolute block inset-0 max-w-none size-full" src={imgBlobInnerDark} />
            </div>
            <div className="absolute h-[343px] left-[860px] top-[338px] w-[645px]" data-node-id="560:3743" />
            <div className="absolute bg-white border border-[#fa4d01] border-solid left-[860px] rounded-[10px] size-[70px] top-[354px]" data-node-id="560:3748" />
            <p className="[word-break:break-word] absolute font-display font-light font-light leading-[normal] left-[948px] text-[24px] text-[var(--ln-ink)] top-[374px] tracking-[-0.28px] whitespace-nowrap" data-node-id="560:3750">
              SOURCE EVIDENCE
            </p>
            <p className="[word-break:break-word] absolute capitalize font-display font-light font-light leading-[53.4px] left-[860px] text-[60px] text-[var(--ln-ink)] top-[435px] tracking-[-3px] w-[374px]" data-node-id="560:3757">
              Know Where Every Finding Came From
            </p>
            <p className="[word-break:break-word] absolute font-body font-normal leading-[19.2px] left-[860px] not-italic text-[16px] text-[var(--ln-ink-70)] top-[607px] tracking-[-0.48px] w-[280px]" data-node-id="560:3759">
              Trace supported findings to the exact file, symbol, lines, and revision.
            </p>
            <div className="absolute bg-white h-[118px] left-[1292px] rounded-[10px] shadow-[-4px_-4px_10px_0px_rgba(0,0,0,0.2),4px_4px_10px_0px_rgba(0,0,0,0.2)] top-[537px] w-[213px]" data-node-id="560:3761" />
            <p className="[word-break:break-word] absolute font-body font-medium inset-[41.94%_8.26%_57.08%_83.36%] leading-[13px] not-italic text-[20px] text-[var(--ln-ink)] tracking-[-0.9px]" data-node-id="560:3778">
              auth.service.ts
            </p>
            <div className="[word-break:break-word] absolute flex flex-col font-body font-normal inset-[44.88%_16.08%_53.84%_81.13%] justify-center leading-[0] not-italic text-[16px] text-[var(--ln-ink)] tracking-[-0.9px]" data-node-id="560:3793">
              <p className="leading-[13px]">login()</p>
            </div>
            <div className="absolute contents inset-[41.42%_17.54%_56.53%_81.13%]" data-node-id="560:3780" data-name="Group">
              <div className="absolute inset-[41.71%_18.87%_56.83%_81.13%]" data-node-id="560:3781" data-name="Vector">
                <div className="absolute inset-[-5.14%_-1px]">
                  <img alt="" className="block max-w-none size-full" src={imgVector27} />
                </div>
              </div>
              <div className="absolute inset-[42.15%_17.54%_56.83%_82.46%]" data-node-id="560:3782" data-name="Vector">
                <div className="absolute inset-[-7.34%_-1px]">
                  <img alt="" className="block max-w-none size-full" src={imgVector28} />
                </div>
              </div>
              <div className="absolute inset-[41.42%_18.09%_58.58%_81.35%]" data-node-id="560:3783" data-name="Vector">
                <div className="absolute inset-[-1px_-11.14%]">
                  <img alt="" className="block max-w-none size-full" src={imgVector29} />
                </div>
              </div>
              <div className="absolute inset-[43.47%_17.76%_56.53%_81.35%]" data-node-id="560:3784" data-name="Vector">
                <div className="absolute inset-[-1px_-6.96%]">
                  <img alt="" className="block max-w-none size-full" src={imgVector30} />
                </div>
              </div>
              <div className="absolute inset-[43.17%_17.54%_56.53%_82.24%]" data-node-id="560:3785" data-name="Vector">
                <div className="absolute inset-[-25.69%_-27.84%]">
                  <img alt="" className="block max-w-none size-full" src={imgVector31} />
                </div>
              </div>
              <div className="absolute flex inset-[43.17%_18.65%_56.53%_81.13%] items-center justify-center" data-node-id="560:3786" style={{ containerType: "size" }}>
                <div className="-scale-x-100 flex-none h-[100cqh] w-[100cqw]">
                  <div className="relative size-full" data-name="Vector">
                    <div className="absolute inset-[-25.69%_-27.84%]">
                      <img alt="" className="block max-w-none size-full" src={imgVector32} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute flex inset-[41.42%_18.65%_58.29%_81.13%] items-center justify-center" data-node-id="560:3787" style={{ containerType: "size" }}>
                <div className="flex-none h-[100cqh] rotate-180 w-[100cqw]">
                  <div className="relative size-full" data-name="Vector">
                    <div className="absolute inset-[-25.71%_-27.84%]">
                      <img alt="" className="block max-w-none size-full" src={imgVector33} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute inset-[41.42%_17.54%_57.85%_81.91%]" data-node-id="560:3788" data-name="Vector">
                <div className="absolute inset-[-10.27%_-11.15%]">
                  <img alt="" className="block max-w-none size-full" src={imgVector34} />
                </div>
              </div>
              <div className="absolute flex inset-[41.86%_17.87%_57.85%_81.91%] items-center justify-center" data-node-id="560:3789" style={{ containerType: "size" }}>
                <div className="-scale-x-100 flex-none h-[100cqh] w-[100cqw]">
                  <div className="relative size-full" data-name="Vector">
                    <div className="absolute inset-[-25.69%_-27.84%]">
                      <img alt="" className="block max-w-none size-full" src={imgVector35} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="absolute inset-[41.42%_18.09%_58.14%_81.91%]" data-node-id="560:3790" data-name="Vector">
                <div className="absolute inset-[-17.13%_-1px]">
                  <img alt="" className="block max-w-none size-full" src={imgVector36} />
                </div>
              </div>
              <div className="absolute inset-[42.15%_17.54%_57.85%_82.13%]" data-node-id="560:3791" data-name="Vector">
                <div className="absolute inset-[-1px_-18.56%]">
                  <img alt="" className="block max-w-none size-full" src={imgVector37} />
                </div>
              </div>
            </div>
            <div className="absolute contents left-[1310.25px] top-[596px]" data-node-id="560:3798">
              <div className="absolute bg-[var(--ln-bar)] h-[17px] left-[1429px] rounded-[5px] top-[596px] w-[62px]" data-node-id="560:3795" />
              <p className="[word-break:break-word] absolute font-body font-normal inset-[45.11%_7.95%_54.07%_89.14%] leading-[13px] not-italic text-[#7a7a7a] text-[10px] tracking-[-0.9px]" data-node-id="560:3796">
                Lines 42–78
              </p>
              <p className="[word-break:break-word] absolute font-body font-normal inset-[47.67%_14.59%_51.51%_81.13%] leading-[13px] not-italic text-[#7a7a7a] text-[10px] text-center tracking-[-0.9px]" data-node-id="560:3800">
                Revision 9f3c7a2
              </p>
              <div className="absolute contents inset-[47.67%_7.51%_51.51%_91.87%]" data-node-id="560:3806" data-name="Group">
                <div className="absolute inset-[47.79%_7.51%_51.51%_91.97%]" data-node-id="560:3807" data-name="Vector">
                  <div className="absolute inset-[-5.35%_-5.98%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector38} />
                  </div>
                </div>
                <div className="absolute inset-[47.67%_7.61%_51.63%_91.87%]" data-node-id="560:3808" data-name="Vector">
                  <div className="absolute inset-[-5.35%_-5.98%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector39} />
                  </div>
                </div>
              </div>
            </div>
            <div className="absolute h-0 left-[1307px] top-[622.5px] w-[184.003px]" data-node-id="560:3799">
              <div className="absolute inset-[-0.5px_0_0_0]">
                <img alt="" className="block max-w-none size-full" src={imgLine5} />
              </div>
            </div>
            <div className="absolute inset-[27.56%_43.2%_69.05%_54.31%]" data-node-id="561:3816" data-name="Vector">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector40} />
            </div>
            <div className="absolute bg-white h-[30px] left-[1324px] rounded-[10px] shadow-[4px_4px_10px_0px_rgba(0,0,0,0.25)] top-[389px] w-[167px]" data-node-id="561:3818" />
            <p className="[word-break:break-word] absolute font-body font-medium inset-[29.89%_10.24%_69.13%_82.87%] leading-[13px] not-italic text-[20px] text-[var(--ln-ink)] tracking-[-0.9px]" data-node-id="561:3819">
              AuthService
            </p>
            <div className="absolute left-[1465px] size-[13px] top-[397px]" data-node-id="561:3822">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgEllipse19} />
            </div>
            <div className="absolute flex inset-[31.85%_12.41%_59.94%_87.15%] items-center justify-center" data-node-id="561:3824" style={{ containerType: "size" }}>
              <div className="flex-none h-[100cqw] rotate-90 w-[100cqh]">
                <div className="relative size-full" data-name="Vector">
                  <div className="absolute inset-[0_0_0_3.45%]">
                    <img alt="" className="block max-w-none size-full" src={imgVector41} />
                  </div>
                </div>
              </div>
            </div>
            <div className="absolute flex inset-[31.63%_18.09%_59.94%_75.05%] items-center justify-center" data-node-id="561:3826" style={{ containerType: "size" }}>
              <div className="flex-none h-[100cqh] rotate-180 w-[100cqw]">
                <div className="relative size-full" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector42} />
                </div>
              </div>
            </div>
            <div className="absolute h-[361px] left-[90px] top-[852px] w-[656px]" data-node-id="562:3828" />
            <div className="absolute bg-white border border-[#fa4d01] border-solid h-[74px] left-[90px] rounded-[10px] top-[869px] w-[72px]" data-node-id="562:3829" />
            <p className="[word-break:break-word] absolute font-display font-light font-light h-[30px] leading-[normal] left-[179px] text-[24px] text-[var(--ln-ink)] top-[890px] tracking-[-0.28px] uppercase w-[281px]" data-node-id="562:3830">
              Engineering Review
            </p>
            <p className="[word-break:break-word] absolute capitalize font-display font-light font-light h-[170px] leading-[0] left-[90px] text-[60px] text-[var(--ln-ink)] top-[954px] tracking-[-3px] w-[410px]" data-node-id="562:3831">
              <span className="leading-[53.4px]">{`Review what `}</span>
              <span className="font-display font-extralight font-extralight leading-[53.4px] text-[#fa4d01]">PARTHA</span>
              <span className="leading-[53.4px]">{` actually found`}</span>
            </p>
            <p className="[word-break:break-word] absolute font-body font-normal h-[41px] leading-[19.2px] left-[90px] not-italic text-[16px] text-[var(--ln-ink-70)] top-[1135px] tracking-[-0.48px] w-[285px]" data-node-id="562:3832">
              See findings alongside their evidence, coverage, and known limits.
            </p>
            <div className="absolute inset-[66.49%_91.06%_30.05%_6.7%]" data-node-id="562:3865" data-name="Vector">
              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector43} />
            </div>
            <div className="absolute contents left-[518px] top-[954px]" data-node-id="562:3931">
              <div className="absolute bg-white h-[196px] left-[518px] rounded-[10px] shadow-[-4px_-4px_10px_0px_rgba(0,0,0,0.25),4px_4px_10px_0px_rgba(0,0,0,0.25)] top-[954px] w-[228px]" data-node-id="562:3916" />
              <div className="absolute contents left-[523px] top-[975px]" data-node-id="562:3918">
                <div className="absolute h-0 left-[523px] top-[1022px] w-[217px]" data-node-id="562:3919">
                  <div className="absolute inset-[-1px_0_0_0]">
                    <img alt="" className="block max-w-none size-full" src={imgLine6} />
                  </div>
                </div>
                <div className="absolute h-0 left-[523px] top-[1081px] w-[217px]" data-node-id="562:3920">
                  <div className="absolute inset-[-1px_0_0_0]">
                    <img alt="" className="block max-w-none size-full" src={imgLine6} />
                  </div>
                </div>
                <div className="absolute inset-[77.94%_64.8%_19.5%_33.09%]" data-node-id="562:3921" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector44} />
                </div>
                <p className="[word-break:break-word] absolute font-body font-medium inset-[74.17%_59.84%_24.85%_35.75%] leading-[13px] not-italic text-[16px] text-[var(--ln-ink)] tracking-[-0.9px]" data-node-id="562:3922">
                  Extracted
                </p>
                <p className="[word-break:break-word] absolute font-body font-medium inset-[78.69%_61.27%_20.33%_35.75%] leading-[13px] not-italic text-[16px] text-[var(--ln-ink)] tracking-[-0.9px]" data-node-id="562:3923">
                  Partial
                </p>
                <p className="[word-break:break-word] absolute font-body font-medium inset-[83.21%_58.66%_15.81%_35.75%] leading-[13px] not-italic text-[16px] text-[var(--ln-ink)] tracking-[-0.9px]" data-node-id="562:3924">
                  Not Assesed
                </p>
                <p className="[word-break:break-word] absolute font-body font-normal inset-[74.25%_54.56%_24.92%_43.02%] leading-[13px] not-italic text-[#7a7a7a] text-[10px] tracking-[-0.9px]" data-node-id="562:3925">
                  213 items
                </p>
                <p className="[word-break:break-word] absolute font-body font-normal inset-[78.77%_54.56%_20.41%_43.2%] leading-[13px] not-italic text-[#7a7a7a] text-[10px] tracking-[-0.9px]" data-node-id="562:3926">
                  30 items
                </p>
                <p className="[word-break:break-word] absolute font-body font-normal inset-[83.28%_54.5%_15.89%_43.33%] leading-[13px] not-italic text-[#7a7a7a] text-[10px] tracking-[-0.9px]" data-node-id="562:3927">
                  73 items
                </p>
                <div className="absolute inset-[73.42%_64.8%_24.02%_33.09%]" data-node-id="562:3928" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector45} />
                </div>
                <div className="absolute inset-[82.38%_64.8%_15.06%_33.09%]" data-node-id="562:3929" data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector46} />
                </div>
              </div>
            </div>
          </div>
          <div className="absolute h-[499px] left-[828px] top-[811px] w-[751px]" data-node-id="562:3999" data-name="product card -4">
            <img alt="" className="theme-light-art absolute block inset-0 max-w-none size-full" src={imgProperty1Default} />
            <img alt="" className="theme-dark-art absolute block inset-0 max-w-none size-full" src={imgCardShapeDark} />
            <div className="absolute content-stretch flex flex-col inset-[8.02%_43.81%_7.82%_0] items-start justify-center pl-[50px] pr-[40px] py-[40px]" data-node-id="562:4001" data-name="Container">
              <div className="content-stretch flex flex-col items-start pb-[8px] relative shrink-0 w-full" data-node-id="562:4002" data-name="Paragraph:margin">
                <div className="content-stretch flex flex-col h-[17px] items-start opacity-70 relative shrink-0 w-full" data-node-id="562:4003" data-name="Paragraph">
                  <p className="[word-break:break-word] font-accent font-normal leading-[0] not-italic relative shrink-0 text-[20px] text-[var(--ln-ink-70)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4004">
                    <span className="leading-[normal]">{`SYSTEM `}</span>
                    <span className="leading-[normal] uppercase">Understanding</span>
                  </p>
                </div>
              </div>
              <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="562:4005" data-name="Heading 2">
                <p className="[word-break:break-word] capitalize font-display font-light font-light leading-[53.4px] relative shrink-0 text-[60px] text-[var(--ln-ink)] tracking-[-3px] w-[416px]" data-node-id="562:4006">
                  turn repository facts into understanding
                </p>
              </div>
              <div className="content-stretch flex flex-col items-start pt-[26px] relative shrink-0 w-full" data-node-id="562:4007" data-name="Paragraph:margin">
                <div className="content-stretch flex flex-col h-[57.609px] items-start opacity-70 relative shrink-0" data-node-id="562:4008" data-name="Paragraph">
                  <p className="[word-break:break-word] font-body font-normal leading-[19.2px] not-italic relative shrink-0 text-[16px] text-[var(--ln-ink-70)] tracking-[-0.48px] w-[280px]" data-node-id="562:4009">
                    Use evidence backed insights to investigate the system and decide what to inspect next.
                  </p>
                </div>
              </div>
            </div>
            <div className="absolute contents inset-[22.85%_2.66%_11.82%_47.54%]" data-node-id="562:4010" style={{ containerType: "size" }}>
              <div className="absolute contents inset-[22.85%_2.66%_11.82%_47.54%]" data-node-id="562:4089" style={{ containerType: "size" }}>
                <div className="absolute flex inset-[43.89%_26.1%_24.85%_72.7%] items-center justify-center" data-node-id="562:4011" style={{ containerType: "size" }}>
                  <div className="flex-none h-[100cqh] rotate-180 w-[100cqw]">
                    <div className="relative size-full" data-name="Vector">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector47} />
                    </div>
                  </div>
                </div>
                <div className="absolute flex inset-[43.89%_30.89%_24.85%_53.4%] items-center justify-center" data-node-id="562:4013" style={{ containerType: "size" }}>
                  <div className="-scale-x-100 flex-none h-[100cqw] rotate-90 w-[100cqh]">
                    <div className="relative size-full" data-name="Vector">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector48} />
                    </div>
                  </div>
                </div>
                <div className="absolute flex inset-[43.89%_8.52%_24.85%_77.5%] items-center justify-center" data-node-id="562:4088" style={{ containerType: "size" }}>
                  <div className="-rotate-90 flex-none h-[100cqw] w-[100cqh]">
                    <div className="relative size-full" data-name="Vector">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgVector49} />
                    </div>
                  </div>
                </div>
                <div className="absolute bg-white border border-[#fa4d01] border-solid inset-[76.15%_12.12%_11.82%_58.85%] rounded-[30px]" data-node-id="562:4016" />
                <div className="absolute contents inset-[22.85%_2.66%_57.11%_84.02%]" data-node-id="562:4026">
                  <div className="absolute bg-white border border-[#fa4d01] border-solid inset-[22.85%_2.66%_57.11%_84.02%] rounded-[30px]" data-node-id="562:4027" />
                  <p className="[word-break:break-word] absolute font-display font-extralight font-extralight inset-[33.87%_8.66%_62.73%_90.01%] leading-[normal] text-[14px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4033">
                    4
                  </p>
                  <p className="[word-break:break-word] absolute font-body font-normal inset-[37.27%_7.72%_59.52%_88.95%] leading-[normal] not-italic text-[12px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4034">
                    Files
                  </p>
                  <div className="absolute inset-[27.86%_7.72%_67.13%_88.95%]" data-node-id="562:4085" data-name="tabler:files-filled">
                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgTablerFilesFilled} />
                  </div>
                </div>
                <div className="absolute contents inset-[22.85%_20.91%_57.11%_65.78%]" data-node-id="562:4035">
                  <div className="absolute bg-white border border-[#fa4d01] border-solid inset-[22.85%_20.91%_57.11%_65.78%] rounded-[30px]" data-node-id="562:4036" />
                  <div className="absolute inset-[27.86%_25.97%_67.13%_70.71%]" data-node-id="562:4082" data-name="carbon:chart-relationship">
                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgCarbonChartRelationship} />
                  </div>
                  <p className="[word-break:break-word] absolute font-display font-extralight font-extralight inset-[33.87%_27.03%_62.73%_71.77%] leading-[normal] text-[14px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4040">
                    8
                  </p>
                  <p className="[word-break:break-word] absolute font-body font-normal inset-[37.27%_22.64%_59.52%_67.38%] leading-[normal] not-italic text-[12px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4041">
                    Relationships
                  </p>
                </div>
                <div className="absolute contents inset-[22.85%_39.15%_57.11%_47.54%]" data-node-id="562:4042">
                  <div className="absolute bg-white border border-[#fa4d01] border-solid inset-[22.85%_39.15%_57.11%_47.54%] rounded-[30px]" data-node-id="562:4043" />
                  <div className="absolute contents inset-[27.86%_43.84%_65.33%_52.33%]" data-node-id="562:4044">
                    <div className="absolute inset-[29.46%_43.84%_67.13%_52.33%]" data-node-id="562:4078" data-name="Group">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgGroup8} />
                    </div>
                    <div className="absolute inset-[27.86%_43.85%_65.33%_52.33%]" data-node-id="562:4045" />
                  </div>
                  <p className="[word-break:break-word] absolute font-display font-extralight font-extralight inset-[33.87%_45.01%_62.73%_53.26%] leading-[normal] text-[14px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4050">{`12 `}</p>
                  <p className="[word-break:break-word] absolute font-body font-normal inset-[37.27%_42.61%_59.52%_51%] leading-[normal] not-italic text-[12px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4051">
                    Symbols
                  </p>
                </div>
                <p className="[word-break:break-word] absolute font-display font-extralight font-extralight inset-[78.76%_14.78%_17.84%_66.31%] leading-[normal] text-[14px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4090">
                  Authentication spans
                </p>
                <p className="[word-break:break-word] absolute font-body font-normal inset-[83.17%_25.97%_13.63%_66.31%] leading-[normal] not-italic text-[12px] text-[var(--ln-ink)] tracking-[-0.28px] whitespace-nowrap" data-node-id="562:4091">
                  4 modules
                </p>
                <div className="absolute inset-[79.76%_35.69%_15.63%_61.25%]" data-node-id="562:4100">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgGroup56} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="absolute contents left-0 top-0" data-node-id="157:30" data-name="NAVBAR">
        <div className="absolute bg-[var(--ln-bar)] h-[133px] left-0 top-0 w-[1728px]" data-node-id="82:2071" />
        <div className="absolute contents left-[78px] top-[40px]" data-node-id="199:1882">
          <a href="#top" aria-label="PARTHA, back to top" onClick={handleBackToTop} className="absolute h-[53px] left-[78px] overflow-clip top-[40px] w-[205px] block cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01]" data-node-id="99:269" data-name="LOGO">
            <div className="absolute inset-[29.04%_1.49%_0.74%_27.17%]" data-node-id="99:270" data-name="Vector">
              <img alt="" className="wordmark-light absolute block inset-0 max-w-none size-full" src={imgVector50} />
                  <img alt="" className="wordmark-dark absolute block inset-0 max-w-none size-full" src={imgWordmarkHeaderDark} />
            </div>
            <div className="absolute contents inset-[18.52%_78.54%_0_0]" data-node-id="99:271" data-name="Clip path group">
              <div className="absolute contents inset-[18.52%_78.54%_0_0]" data-node-id="99:274" data-name="Group">
                <div className="absolute inset-[18.52%_78.54%_0_0] mask-alpha mask-intersect mask-no-clip mask-no-repeat mask-size-[44px_43.185px]" data-node-id="99:275" style={{ maskImage: `url("${imgVector51}")` }} data-name="Vector">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" height="43.185" src={imgVector52} width="44" />
                </div>
              </div>
            </div>
          </a>
          <div className="absolute contents left-[463px] top-[40px]" data-node-id="88:1536" data-name="Navbar 2">
            <div className="absolute bg-[var(--ln-bar)] h-[52px] left-[463px] top-[40px] w-[669px]" data-node-id="87:1523" />
            <a href="#product" className="-translate-x-1/2 [word-break:break-word] absolute block capitalize cursor-pointer font-display font-medium font-medium h-[19.007px] leading-[0] left-[541.5px] text-[24px] text-[var(--ln-ink)] text-center top-[51.99px] w-[103px]" data-node-id="87:1520">
              <p className="leading-[normal]">Product</p>
            </a>
            <a href="#how-it-works" className="-translate-x-1/2 [word-break:break-word] absolute block capitalize cursor-pointer font-display font-medium font-medium h-[28.01px] leading-[0] left-[727.5px] text-[24px] text-[var(--ln-ink)] text-center top-[51.99px] w-[177px]" data-node-id="87:1524">
              <p className="leading-[normal]">How it works</p>
            </a>
            <a href="#capabilities" className="-translate-x-1/2 [word-break:break-word] absolute block capitalize cursor-pointer font-display font-medium font-medium h-[28.01px] leading-[0] left-[931px] text-[24px] text-[var(--ln-ink)] text-center top-[51.99px] w-[152px]" data-node-id="87:1526">
              <p className="leading-[normal]">Capabilities</p>
            </a>
            <a href="#faq" className="-translate-x-1/2 [word-break:break-word] absolute block capitalize cursor-pointer font-display font-medium font-medium h-[28px] leading-[0] left-[1073px] text-[24px] text-[var(--ln-ink)] text-center top-[52px] w-[54px]" data-node-id="87:1528">
              <p className="leading-[normal]">FAQ</p>
            </a>
          </div>
          <Link to={nav.login} className="-translate-x-1/2 [word-break:break-word] absolute block capitalize cursor-pointer font-display font-medium font-medium h-[28px] leading-[0] left-[1366.5px] text-[24px] text-[var(--ln-ink)] text-center top-[53px] w-[83px]" data-node-id="87:1530">
            <p className="leading-[normal]">Log In</p>
          </Link>
          <Link to={nav.register} className="group absolute block cursor-pointer h-[52px] left-[1418px] top-[41px] w-[232px]" data-node-id="128:99" data-name="Button-sign up">
            <div className="absolute bg-[#fffcf7] border-3 border-[#fa4d01] border-solid inset-0 rounded-[25px] transition-colors duration-200 group-hover:bg-[#fa4d01] group-focus-visible:bg-[#fa4d01] motion-reduce:transition-none" data-node-id="I128:99;128:68" />
            <p className="[word-break:break-word] absolute capitalize font-display font-medium font-medium inset-[21.15%_7.93%_19.27%_7.93%] leading-[normal] text-[#fa4d01] transition-colors duration-200 group-hover:text-white group-focus-visible:text-white motion-reduce:transition-none text-[24px] text-center" data-node-id="I128:99;128:69">
              Create account
            </p>
          </Link>
        </div>
      </div>
    </div>
  );
}