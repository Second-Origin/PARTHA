import { useState } from 'react';

import { FAQ_SECTION } from '@/data/landing';
import { faqAnswers, faqQuestions } from '@/data/faq';
import { cn } from '@/utils/cn';

/** The FAQ accordion.
 *
 * The design shows six collapsed rows inside one bordered card. This is a real
 * accordion: `<button>` headers toggling `<region>` panels, one open at a time,
 * fully keyboard operable. The previous implementation opened a modal from an
 * invisible hotspot, which is neither what was designed nor navigable. */
export function Faq() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" className="bg-[var(--ln-page)] pb-[80px] pt-[40px] lg:pb-[110px] lg:pt-[60px]">
      <div className="mx-auto grid w-full max-w-[1568px] gap-10 px-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] lg:gap-[70px] lg:px-10">
        <header>
          <p className="font-display text-[24px] font-extralight text-[var(--ln-ink-soft)] lg:text-[30px]">
            {FAQ_SECTION.eyebrow}
          </p>
          <h2 className="mt-3 font-display text-[30px] font-light leading-[1.2] text-[var(--ln-ink)] lg:text-[43px]">
            {FAQ_SECTION.heading}
          </h2>
        </header>

        <div className="overflow-hidden rounded-[18px] border border-primary/30">
          {faqQuestions.map((question, index) => {
            const isOpen = open === index;
            const panelId = `faq-panel-${index}`;
            const buttonId = `faq-button-${index}`;

            return (
              <div key={question} className={cn(index > 0 && 'border-t border-primary/20')}>
                <h3>
                  <button
                    type="button"
                    id={buttonId}
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => setOpen(isOpen ? null : index)}
                    className="flex w-full items-center justify-between gap-6 px-6 py-[19px] text-left font-display text-[15px] font-semibold text-[var(--ln-ink)] transition-colors hover:bg-[var(--ln-quote)]/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary lg:px-8 lg:text-[17px]"
                  >
                    {question}
                    <svg
                      aria-hidden
                      viewBox="0 0 24 24"
                      className={cn(
                        'size-[20px] shrink-0 fill-none stroke-[var(--ln-ink-soft)] stroke-[2] transition-transform duration-200',
                        isOpen && 'rotate-180',
                      )}
                    >
                      <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                </h3>

                <div
                  id={panelId}
                  role="region"
                  aria-labelledby={buttonId}
                  hidden={!isOpen}
                  className="px-6 pb-[22px] lg:px-8"
                >
                  <p className="max-w-[70ch] font-sans text-[15px] leading-[1.55] text-[var(--ln-ink-soft)] lg:text-[16px]">
                    {faqAnswers[index]}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
