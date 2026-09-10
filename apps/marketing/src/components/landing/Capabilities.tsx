import { useState } from 'react';

import decorative from '@/assets/landing/decorative.svg';
import iconRelationship from '@/assets/landing/figma/carbon-chart-relationship.svg';
import iconGuarantee from '@/assets/landing/figma/guarantee.png';
import iconInformatics from '@/assets/landing/figma/informatics.png';
import iconForked from '@/assets/landing/figma/octicon-repo-forked24.svg';
import iconEvidence from '@/assets/landing/figma/piece-of-evidence.png';
import iconSealed from '@/assets/landing/figma/secured-package.png';
import { CAPABILITIES } from '@/data/landing';

/** One glyph per capability, in registry order. */
const ICONS = [iconForked, iconEvidence, iconSealed, iconInformatics, iconRelationship, iconGuarantee];

const COUNT = CAPABILITIES.items.length;

/** The capability carousel.
 *
 * The design shows three things at once: the active capability (left, tinted),
 * its quote (centre), and the one you'd land on next (right, neutral). The two
 * orange tiles between them are Previous and Next, interlocking as a pinwheel.
 *
 * Both controls wrap, so the set is a loop with no dead end. The quote region
 * is a live region: screen-reader users hear the new capability announced
 * rather than silently losing the change. */
export function Capabilities() {
  const [index, setIndex] = useState(0);

  const go = (delta: number) => setIndex((current) => (current + delta + COUNT) % COUNT);

  const active = CAPABILITIES.items[index];
  const upcoming = CAPABILITIES.items[(index + 1) % COUNT];

  return (
    <section id="capabilities" className="relative overflow-hidden bg-[var(--ln-page)] pb-[80px] pt-[50px] lg:pb-[120px] lg:pt-[70px]">
      <div className="mx-auto w-full max-w-[1568px] px-6 lg:px-10">
        <h2 className="text-center font-display text-[28px] font-extralight text-[var(--ln-ink)] lg:text-[36px]">
          {CAPABILITIES.heading}
        </h2>

        <div className="relative mt-[40px] grid gap-5 lg:mt-[58px] lg:grid-cols-[290px_minmax(0,1fr)_420px] lg:items-stretch lg:gap-6">
          {/* Left rail: the section's promise, then the active capability. */}
          <div className="flex flex-col gap-5">
            <div className="rounded-[26px] border border-primary bg-[var(--ln-card)] p-7">
              <p className="font-display text-[22px] font-extralight text-[var(--ln-ink-soft)] lg:text-[27px]">
                {CAPABILITIES.eyebrow}
              </p>
              <p className="mt-2 font-display text-[16px] font-semibold leading-[1.3] text-[var(--ln-ink)] lg:text-[19px]">
                {CAPABILITIES.intro}
              </p>
            </div>

            <div className="flex flex-1 flex-col items-center justify-center gap-5 rounded-[26px] bg-[var(--ln-tint-blue)] p-8">
              <span aria-hidden className="grid size-[52px] place-items-center overflow-clip rounded-[13px] bg-[var(--ln-blue-tile)] p-[11px]">
                <img src={ICONS[index]} alt="" className="size-full object-contain" />
              </span>
              <p className="text-center font-display text-[16px] font-bold leading-[1.25] text-[var(--ln-blue-ink)] lg:text-[18px]">
                {active.label}
              </p>
            </div>
          </div>

          {/* Centre: the quote for the active capability. */}
          <blockquote
            aria-live="polite"
            className="flex min-h-[260px] flex-col rounded-[26px] bg-[var(--ln-quote)] p-8 lg:p-11"
          >
            <span aria-hidden className="font-display text-[44px] font-bold leading-none text-primary">
              &ldquo;
            </span>
            <p className="mt-5 max-w-[36ch] font-sans text-[18px] leading-[1.45] text-[var(--ln-ink)] lg:text-[22px]">
              {active.quote}
            </p>
            <p className="sr-only">{`Capability ${index + 1} of ${COUNT}: ${active.label}.`}</p>
          </blockquote>

          {/* Right: the interlocking Previous / Next pinwheel plus a preview of
              the capability the Next control leads to. */}
          <div className="relative grid grid-cols-2 grid-rows-2 gap-3">
            <img
              aria-hidden
              src={decorative}
              alt=""
              className="pointer-events-none absolute -left-[86px] top-[26%] hidden w-[120px] lg:block"
            />

            <button
              type="button"
              onClick={() => go(1)}
              className="col-start-2 row-start-1 flex items-center justify-between gap-3 rounded-[26px] bg-primary px-6 py-7 text-left font-display text-[17px] font-medium text-white transition-colors hover:bg-[#d94301] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary lg:text-[19px]"
            >
              Next
              <svg aria-hidden viewBox="0 0 24 24" className="size-[22px] shrink-0 fill-none stroke-current stroke-[2.2]">
                <path d="M4 12h15M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="sr-only">{`: ${upcoming.label}`}</span>
            </button>

            <button
              type="button"
              onClick={() => go(-1)}
              className="col-start-1 row-start-2 flex items-center gap-3 rounded-[26px] bg-primary px-6 py-7 text-left font-display text-[17px] font-medium text-white transition-colors hover:bg-[#d94301] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary lg:text-[19px]"
            >
              <svg aria-hidden viewBox="0 0 24 24" className="size-[22px] shrink-0 fill-none stroke-current stroke-[2.2]">
                <path d="M20 12H5M11 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Previous
            </button>

            <div
              aria-hidden
              className="col-start-2 row-start-2 flex flex-col items-center justify-center gap-5 rounded-[26px] bg-[var(--ln-grey)] p-7"
            >
              <span className="grid size-[52px] place-items-center overflow-clip rounded-[13px] bg-[var(--ln-plum-tile)] p-[11px]">
                <img src={ICONS[(index + 1) % COUNT]} alt="" className="size-full object-contain" />
              </span>
              <p className="text-center font-display text-[15px] font-bold leading-[1.25] text-[var(--ln-ink)] lg:text-[17px]">
                {upcoming.label}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
