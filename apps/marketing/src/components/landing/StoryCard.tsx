import { useCallback, useEffect, useState } from 'react';

import v1Connectors from '@/assets/landing/story/v1-connectors.svg';
import v1ConnectorsDark from '@/assets/landing/story/v1-connectors-dark.svg';
import v1IconApi from '@/assets/landing/story/v1-icon-api.svg';
import v1IconAuth from '@/assets/landing/story/v1-icon-auth.svg';
import v1IconDb from '@/assets/landing/story/v1-icon-db.svg';
import v1IconUser from '@/assets/landing/story/v1-icon-user.svg';
import v1IconWeb from '@/assets/landing/story/v1-icon-web.svg';
import v2Connectors from '@/assets/landing/story/v2-connectors.svg';
import v2ConnectorsDark from '@/assets/landing/story/v2-connectors-dark.svg';
import v2IconApi from '@/assets/landing/story/v2-icon-api.svg';
import v2IconAuth from '@/assets/landing/story/v2-icon-auth.svg';
import v2IconDb from '@/assets/landing/story/v2-icon-db.svg';
import v2IconWeb from '@/assets/landing/story/v2-icon-web.svg';
import v3Connectors from '@/assets/landing/story/v3-connectors.svg';
import v3ConnectorsDark from '@/assets/landing/story/v3-connectors-dark.svg';
import v3IconApi from '@/assets/landing/story/v3-icon-api.svg';
import v3IconAuth from '@/assets/landing/story/v3-icon-auth.svg';
import v3IconDb from '@/assets/landing/story/v3-icon-db.svg';
import v3IconUser from '@/assets/landing/story/v3-icon-user.svg';
import v3IconWeb from '@/assets/landing/story/v3-icon-web.svg';
import v3NpmLogo from '@/assets/landing/story/v3-npm-logo.svg';

/* The three states of the "product card -1" component set
 * (Figma f1HlSxjl8pvvOm86XFPZEJ, node 555:2477 — Property 1 = Default /
 * Variant2 / Variant3). Every number below is the design's own geometry,
 * measured off the exported component-set SVG and expressed relative to the
 * 751x499 card, so the three states line up pixel-for-pixel as they do in
 * Figma. The three dots at the bottom are the state indicator: the design
 * cycles the card through the states, which is why they sit outside the
 * cross-fading layers and drive the rotation here. */

const CARD_W = 751;
const CARD_H = 499;

/** Milliseconds between state changes.
 *
 * Measured off the prototype recording: successive cross-fades land 1.5s
 * apart, each taking roughly half a second, so a state is fully settled for
 * about a second before the next one starts. Figma exports no timing for a
 * variant swap, so this came from the video rather than the file. Retiming the
 * whole rotation is this constant plus the duration on the layer below. */
const HOLD_MS = 1500;

const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';

function prefersReducedMotion() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia(REDUCED_MOTION).matches;
}

type Icon = { src: string; dx: number; dy: number; w: number; h: number };

/* Icon offsets are relative to the 99x99 node box and are identical wherever
 * the same icon appears, so they travel with the icon rather than the node. */
const ICON = {
  db: (src: string): Icon => ({ src, dx: 36, dy: 16, w: 27.27, h: 32.61 }),
  user: (src: string): Icon => ({ src, dx: 32.8, dy: 16.8, w: 33.31, h: 31.4 }),
  auth: (src: string): Icon => ({ src, dx: 36.05, dy: 16.19, w: 27.27, h: 32.61 }),
  web: (src: string): Icon => ({ src, dx: 33.5, dy: 15.5, w: 32, h: 33.61 }),
  api: (src: string): Icon => ({ src, dx: 35.5, dy: 15.5, w: 28.27, h: 33.61 }),
};

type NodeSpec = { left: number; top: number; name: string; tech: string; icon: Icon };

/** One service in the diagram: a 99x99 white tile with an orange border, the
 * icon near the top and two lines of label underneath. The 54.5 / 71.5 label
 * offsets are constant across every node in every state of the design. */
function ServiceNode({ left, top, name, tech, icon }: NodeSpec) {
  return (
    <div className="absolute" style={{ left, top, width: 99, height: 99 }}>
      <div className="absolute inset-0 rounded-[30px] border border-solid border-[#fa4d01] bg-white" />
      <img
        alt=""
        className="absolute block max-w-none"
        src={icon.src}
        style={{ left: icon.dx, top: icon.dy, width: icon.w, height: icon.h }}
      />
      <p className="absolute left-0 right-0 top-[54.5px] text-center font-display text-[14px] font-extralight leading-[normal] tracking-[-0.28px] text-black">
        {name}
      </p>
      <p className="absolute left-0 right-0 top-[71.5px] text-center font-sans text-[12px] font-normal not-italic leading-[normal] tracking-[-0.28px] text-black">
        {tech}
      </p>
    </div>
  );
}

type Variant = {
  id: string;
  eyebrow: string;
  heading: string;
  body: string;
  connectors: { light: string; dark: string; left: number; top: number; w: number; h: number };
  nodes: NodeSpec[];
  /** State-specific furniture that only one variant has. */
  extra?: React.ReactNode;
};

const REQUEST_PATH = ['Web UI', 'API Gateway', 'Auth', 'Database'];

/* Variant 2 pairs the diagram with a request summary: a rounded panel holding
 * the request line, its "Supported" badge, and the resolved path. */
function RequestPanel() {
  return (
    <div className="absolute" style={{ left: 386.5, top: 334.5, width: 304, height: 77 }}>
      <div className="absolute inset-0 rounded-[30px] border border-solid border-[#fa4d01] bg-white" />
      <p className="absolute left-[14px] top-[10px] font-display text-[14px] font-normal leading-[normal] tracking-[-0.28px] text-black">
        Request
      </p>
      <p className="absolute left-[82px] top-[10px] font-sans text-[13px] font-normal not-italic leading-[normal] tracking-[-0.28px] text-black">
        POST/Login
      </p>
      <div
        className="absolute rounded-[8.5px]"
        style={{ left: 202.5, top: 8.5, width: 81, height: 17, backgroundColor: 'rgba(27,118,0,0.2)' }}
      />
      <p
        className="absolute text-center font-sans text-[10px] font-normal not-italic leading-[17px] tracking-[-0.2px]"
        style={{ left: 202.5, top: 8.5, width: 81, color: '#1B7600' }}
      >
        Supported
      </p>
      <p className="absolute left-[14px] top-[40px] font-display text-[14px] font-normal leading-[normal] tracking-[-0.28px] text-black">
        Path
      </p>
      <p
        className="absolute font-sans text-[12px] font-normal not-italic leading-[14.4px] tracking-[-0.24px] text-black"
        style={{ left: 81, top: 38, width: 196 }}
      >
        {REQUEST_PATH.map((hop, i) => (
          <span key={hop}>
            {hop}
            {i < REQUEST_PATH.length - 1 && (
              /* Non-breaking space before the arrow so a wrap lands after it,
                 the way the design breaks this row. */
              <span className="text-[#fa4d01]">{'\u00a0\u2192 '}</span>
            )}
          </span>
        ))}
      </p>
    </div>
  );
}

/* Variant 3 labels the two sides of the tree and hangs one external package
 * off the bottom, to show that dependencies leave the repository too. */
function DependencyFurniture() {
  const label =
    'absolute font-sans text-[12px] font-normal not-italic leading-[normal] tracking-[-0.24px] text-[var(--story-ink-soft)]';
  return (
    <>
      <p className={label} style={{ left: 392.5, top: 24 }}>
        Depends On
      </p>
      <p className={label} style={{ left: 617.4, top: 24 }}>
        Used By
      </p>
      <p className={label} style={{ left: 468.5, top: 353 }}>
        External Dependencies
      </p>
      <div className="absolute" style={{ left: 467.5, top: 371.5, width: 131, height: 99 }}>
        <div className="absolute inset-0 rounded-[30px] border border-solid border-[#fa4d01] bg-white" />
        <img
          alt=""
          className="absolute block max-w-none"
          src={v3NpmLogo}
          style={{ left: 49, top: 16, width: 33, height: 33 }}
        />
        <p className="absolute left-0 right-0 top-[54.5px] text-center font-display text-[14px] font-extralight leading-[normal] tracking-[-0.28px] text-black">
          jsonwebtoken
        </p>
        <p className="absolute left-0 right-0 top-[71.5px] text-center font-sans text-[12px] font-normal not-italic leading-[normal] tracking-[-0.28px] text-black">
          npm package
        </p>
      </div>
    </>
  );
}

const VARIANTS: Variant[] = [
  {
    id: 'system-view',
    eyebrow: 'SYSTEM VIEW',
    heading: 'see how the system fits together',
    body: 'Understand modules, dependencies, routes, and, relationships from one repository model.',
    connectors: { light: v1Connectors, dark: v1ConnectorsDark, left: 477.62, top: 80.5, w: 177.88, h: 339 },
    nodes: [
      { left: 488.5, top: 31.5, name: 'Database', tech: 'MySQL', icon: ICON.db(v1IconDb) },
      { left: 376.5, top: 131.5, name: 'User Service', tech: 'Python', icon: ICON.user(v1IconUser) },
      { left: 588.5, top: 200.5, name: 'Auth Service', tech: 'Spring Boot', icon: ICON.auth(v1IconAuth) },
      { left: 376.5, top: 268.5, name: 'Web UI', tech: 'Next.js', icon: ICON.web(v1IconWeb) },
      { left: 488.5, top: 368.5, name: 'API Gateway', tech: 'Node.js', icon: ICON.api(v1IconApi) },
    ],
  },
  {
    id: 'request-flow',
    eyebrow: 'REQUEST FLOW',
    heading: 'follow how a request moves',
    body: 'Trace a supported request path across services and inspect the relationships that connect each step.',
    connectors: { light: v2Connectors, dark: v2ConnectorsDark, left: 425.5, top: 167.5, w: 220, h: 109 },
    nodes: [
      { left: 382.5, top: 65.5, name: 'Web UI', tech: 'Next.js', icon: ICON.web(v2IconWeb) },
      { left: 591.5, top: 65.5, name: 'Database', tech: 'MySQL', icon: ICON.db(v2IconDb) },
      { left: 382.5, top: 216.5, name: 'API Gateway', tech: 'Node.js', icon: ICON.api(v2IconApi) },
      { left: 591.5, top: 216.5, name: 'Auth Service', tech: 'Spring Boot', icon: ICON.auth(v2IconAuth) },
    ],
    extra: <RequestPanel />,
  },
  {
    id: 'dependency-view',
    eyebrow: 'DEPENDENCY VIEW',
    heading: 'see what depends on what',
    body: 'Explore internal and external dependencies to understand what a module relies on and what relies on it.',
    connectors: { light: v3Connectors, dark: v3ConnectorsDark, left: 481.5, top: 86.5, w: 105, h: 261 },
    nodes: [
      { left: 378.5, top: 48.5, name: 'API Gateway', tech: 'Node.js', icon: ICON.api(v3IconApi) },
      { left: 590.5, top: 48.5, name: 'Web UI', tech: 'Next.js', icon: ICON.web(v3IconWeb) },
      { left: 485.5, top: 132.5, name: 'Auth Service', tech: 'Spring Boot', icon: ICON.auth(v3IconAuth) },
      { left: 378.5, top: 219.5, name: 'User Service', tech: 'Python', icon: ICON.user(v3IconUser) },
      { left: 590.5, top: 219.5, name: 'Database', tech: 'MySQL', icon: ICON.db(v3IconDb) },
    ],
    extra: <DependencyFurniture />,
  },
];

function VariantLayer({ variant }: { variant: Variant }) {
  const { connectors } = variant;
  return (
    <>
      {/* Left column: the design's own flex container, inset 8.02% / 43.81% /
          7.82% / 0 against the card with 80px of left padding. */}
      <div className="absolute inset-[8.02%_43.81%_7.82%_0] flex flex-col content-stretch items-start justify-center py-[40px] pl-[80px] pr-[40px]">
        <div className="relative flex w-full shrink-0 flex-col content-stretch items-start pb-[8px]">
          <div className="relative flex h-[17px] w-full shrink-0 flex-col content-stretch items-start opacity-70">
            <p className="relative shrink-0 whitespace-nowrap font-accent text-[20px] font-normal not-italic leading-[normal] tracking-[-0.28px] text-[var(--story-ink-soft)] [word-break:break-word]">
              {variant.eyebrow}
            </p>
          </div>
        </div>
        <div className="relative flex w-full shrink-0 flex-col content-stretch items-start">
          <p className="relative w-full shrink-0 font-display text-[60px] font-light capitalize leading-[53.4px] tracking-[-3px] text-[var(--story-ink)] [word-break:break-word]">
            {variant.heading}
          </p>
        </div>
        <div className="relative flex w-full shrink-0 flex-col content-stretch items-start pt-[26px]">
          <div className="relative flex shrink-0 flex-col content-stretch items-start opacity-70">
            <p className="relative w-[280px] shrink-0 font-sans text-[16px] font-normal not-italic leading-[19.2px] tracking-[-0.48px] text-[var(--story-ink-soft)] [word-break:break-word]">
              {variant.body}
            </p>
          </div>
        </div>
      </div>

      {/* Connector artwork. Two copies rather than a JS theme lookup so the
          correct one is already painted on the very first frame. */}
      <img
        alt=""
        className="story-connectors-light absolute block max-w-none"
        src={connectors.light}
        style={{ left: connectors.left, top: connectors.top, width: connectors.w, height: connectors.h }}
      />
      <img
        alt=""
        className="story-connectors-dark absolute block max-w-none"
        src={connectors.dark}
        style={{ left: connectors.left, top: connectors.top, width: connectors.w, height: connectors.h }}
      />

      {variant.nodes.map((node) => (
        <ServiceNode key={`${node.name}-${node.left}-${node.top}`} {...node} />
      ))}
      {variant.extra}
    </>
  );
}

/** The three-state product card, rotating the way the design's prototype does.
 *
 * Rotation pauses while the pointer is over the card or focus is inside it, so
 * it never pulls a slide out from under someone mid-read, and it does not run
 * at all under `prefers-reduced-motion` — the dots stay operable in that case,
 * which keeps every state reachable without motion. */
export function StoryCard({ className }: { className?: string }) {
  const [index, setIndex] = useState(0);
  const [held, setHeld] = useState(false);
  /* Read during state initialisation so the first paint already honours the
     preference, then kept in sync in case the visitor changes it. */
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia(REDUCED_MOTION);
    const sync = () => setReducedMotion(query.matches);
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (held || reducedMotion) return;
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % VARIANTS.length), HOLD_MS);
    return () => window.clearInterval(timer);
  }, [held, reducedMotion]);

  const hold = useCallback(() => setHeld(true), []);
  const release = useCallback(() => setHeld(false), []);

  return (
    <div
      className={className ?? 'relative'}
      data-node-id="555:2477"
      style={{ width: CARD_W, height: CARD_H }}
      onMouseEnter={hold}
      onMouseLeave={release}
      onFocusCapture={hold}
      onBlurCapture={release}
    >
      <div className="absolute inset-0 rounded-[110px] bg-[var(--story-surface)]" />

      {VARIANTS.map((variant, i) => (
        <div
          key={variant.id}
          className="absolute inset-0 transition-opacity duration-500 ease-out motion-reduce:transition-none"
          style={{ opacity: i === index ? 1 : 0, pointerEvents: i === index ? undefined : 'none' }}
          aria-hidden={i !== index}
        >
          <VariantLayer variant={variant} />
        </div>
      ))}

      {/* The state indicator. It sits above the cross-fading layers because it
          is shared furniture, not part of any one state. */}
      <div className="absolute" style={{ left: 344.5, top: 468, width: 61.7, height: 14 }}>
        {VARIANTS.map((variant, i) => (
          <button
            key={variant.id}
            type="button"
            className="absolute rounded-full transition-colors duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01] motion-reduce:transition-none"
            style={{
              left: i * 23.632,
              top: 0,
              width: 14.69,
              height: 14,
              backgroundColor: i === index ? '#FA4D01' : 'var(--story-dot-idle)',
            }}
            aria-label={`Show ${variant.eyebrow.toLowerCase()}`}
            aria-current={i === index}
            onClick={() => setIndex(i)}
          />
        ))}
      </div>
    </div>
  );
}
