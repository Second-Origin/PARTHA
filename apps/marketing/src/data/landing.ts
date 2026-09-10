/** Copy for the landing page, transcribed from the iteration-1 Figma design
 * (file f1HlSxjl8pvvOm86XFPZEJ, frame "Landing Page" 1:2). FAQ text lives in
 * `faq.ts` and footer structure in `site.ts`; this file holds everything else
 * so the section components stay layout-only. */

import storySystem from '@/assets/landing/story-system.svg';
import storyEvidence from '@/assets/landing/story-evidence.svg';
import storyReview from '@/assets/landing/story-review.svg';
import storyUnderstanding from '@/assets/landing/story-understanding.svg';
import step1 from '@/assets/landing/step-1.svg';
import step2 from '@/assets/landing/step-2.svg';
import step3 from '@/assets/landing/step-3.svg';
import step4 from '@/assets/landing/step-4.svg';

export const NAV_LINKS = [
  { label: 'Product', href: '#product' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Capabilities', href: '#capabilities' },
  { label: 'FAQ', href: '#faq' },
] as const;

export const HERO = {
  eyebrow: 'Repository Intelligence System',
  headingLine1: 'Reveal The',
  headingLine2: 'System',
  headingLine3: 'Behind The Code.',
  body: 'PARTHA analyzes a Git repository at a specific revision and produces a sealed, evidence-backed model of the system. Deterministic. Reproducible. Honest about its limits.',
  primaryCta: 'Analyze a Repository',
  secondaryCta: 'See how it works',
  footnote: 'Connect a repository. PARTHA maps the system. You verify the evidence.',
} as const;

export const MEET = {
  lead: 'Meet',
  brand: 'Partha',
  sub: 'Understand your codebase',
} as const;

/** The four interlocking product cards. `tone` selects the card shape/colour
 * pair; the design alternates blue and peach in a 2x2 pinwheel. `highlight`,
 * where present, is the word the design sets in the brand orange. */
export const STORY_CARDS = [
  {
    tone: 'blue',
    eyebrow: 'System view',
    heading: 'See how the system fits together',
    body: 'Understand modules, dependencies, routes, and relationships from one repository model.',
    image: storySystem,
    alt: 'Services and modules resolving into one sealed repository model',
  },
  {
    tone: 'peach',
    eyebrow: 'Source evidence',
    heading: 'Know where every finding came from',
    body: 'Trace supported findings to the exact file, symbol, lines, and revision.',
    image: storyEvidence,
    alt: 'A finding traced to auth.service.ts, login(), lines 42 to 78, revision 9f3c7a2',
  },
  {
    tone: 'peach',
    eyebrow: 'Engineering review',
    heading: 'Review what PARTHA actually found',
    highlight: 'PARTHA',
    body: 'See findings alongside their evidence, coverage, and known limits.',
    image: storyReview,
    alt: 'Coverage reported as extracted, partial, and not assessed',
  },
  {
    tone: 'blue',
    eyebrow: 'System understanding',
    heading: 'Turn repository facts into understanding',
    body: 'Use evidence-backed insights to investigate the system and decide what to inspect next.',
    image: storyUnderstanding,
    alt: 'Symbols, relationships, and files resolving into an authentication span across four modules',
  },
] as const;

export const HOW_IT_WORKS = {
  eyebrow: 'How Partha Works',
  heading: 'From code to clarity',
  steps: [
    {
      tone: 'blue',
      kicker: 'Import repository',
      heading: 'Select your source',
      body: 'Connect a repository, choose the revision you want to analyze, and let PARTHA create a sealed snapshot tied to that exact version.',
      image: step1,
      alt: 'A repository and revision resolving into a sealed snapshot',
    },
    {
      tone: 'grey',
      kicker: 'PARTHA analyzes',
      heading: 'We extract, map, & connect',
      body: "PARTHA maps the repository's files, symbols, routes, dependencies, and relationships while generating evidence for the supported parts of the system.",
      image: step2,
      alt: 'Files, symbols, dependencies, and relationships feeding the model',
    },
    {
      tone: 'sand',
      kicker: 'Explore & verify',
      heading: 'Navigate the system with evidence',
      body: 'Explore the architecture and relationships, then trace supported findings back to the exact file, symbol, line range, and revision that produced them.',
      image: step3,
      alt: 'A finding traced back to auth.service.ts at lines 42 to 78',
    },
    {
      tone: 'orange',
      kicker: 'Review & act',
      heading: 'Make confident engineering decisions',
      body: 'Use evidence-backed findings, insights, documentation, and exports to understand the system and make engineering decisions with clear visibility into what was and was not assessed.',
      image: step4,
      alt: 'A verified shield',
    },
  ],
} as const;

export const CAPABILITIES = {
  eyebrow: 'Capabilities',
  heading: 'What Is PARTHA Capable Of',
  intro: 'Built to be trusted by the people reading the diff.',
  trustLabel: 'Trusted by builders',
  items: [
    {
      label: 'Deterministic extraction',
      quote: 'Same repo + same revision → byte-identical model. No sampling, no temperature, no drift.',
    },
    {
      label: 'Evidence backed',
      quote: 'Every claim traces to file, line, symbol. No hallucinated APIs, no fabricated call sites.',
    },
    {
      label: 'Sealed models',
      quote: 'Content-addressed and signed. Reproducible across machines, CI, and time.',
    },
    {
      label: 'Language coverage matrix',
      quote: 'Deep extraction for supported Python and TypeScript/JavaScript constructs; everything else is reported, not guessed.',
    },
    {
      label: 'Relationship graph',
      quote: 'Symbols, calls, imports, ownership, and dependencies as first-class edges.',
    },
    {
      label: 'Honest about limits',
      quote: 'Dynamic dispatch, reflection, and generated code are flagged, not guessed.',
    },
  ],
} as const;

export const FAQ_SECTION = {
  eyebrow: 'FAQ',
  heading: 'Questions Engineers actually ask',
} as const;

export const CTA = {
  heading: 'Understand the system behind the code.',
  body: "PARTHA is currently in private preview with a small group of engineering teams. Request access and we'll follow up with onboarding materials and a self-hosted install guide.",
  primary: 'Analyze a Repository',
  secondary: 'Get in touch with us',
} as const;

export const FOOTER_TAGLINE =
  'Deterministic repository intelligence. Sealed, evidence-backed models of the system behind the code.';

export const FOOTER_COPYRIGHT = 'All rights reserved. Copyright © 2026 Partha';
