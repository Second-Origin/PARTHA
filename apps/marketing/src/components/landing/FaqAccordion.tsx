import { useState } from 'react';

import imgIcon from '@/assets/landing/figma/icon.svg';
import { faqAnswers, faqQuestions } from '@/data/faq';

/* The FAQ list from the design's own component set (Figma node 480:8100).
 * Its three exported states are: every row closed, the first row open, and the
 * second row open -- one answer at a time, the rest staying closed. That is
 * what this implements: a single-open accordion, 57px per closed row, the open
 * row growing by the height of its answer.
 *
 * The 95px of canvas below the list is what bounds this: one open two-line
 * answer fits inside it, two would not, which is the other reason opening a
 * row closes the previous one. */

const ROW_H = 56;

export function FaqAccordion({ id, className }: { id?: string; className?: string }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div id={id} className={className} data-node-id="480:8100" data-name="FAQ">
      {faqQuestions.map((question, i) => {
        const open = openIndex === i;
        return (
          <div
            key={question}
            className={i > 0 ? 'border-t border-solid border-[rgba(250,77,1,0.2)]' : undefined}
          >
            <h3>
              <button
                type="button"
                id={`faq-question-${i}`}
                aria-expanded={open}
                aria-controls={`faq-answer-${i}`}
                onClick={() => setOpenIndex(open ? null : i)}
                className="relative flex w-full cursor-pointer items-center px-[20px] text-left focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#fa4d01]"
                style={{ height: ROW_H }}
              >
                <span className="font-display text-[20px] font-semibold leading-[22.5px] text-[var(--ln-faq-ink)]">
                  {question}
                </span>
                <span
                  className="absolute right-[27px] top-[16px] grid size-[24px] place-items-center transition-transform duration-300 motion-reduce:transition-none"
                  style={{ transform: open ? 'rotate(180deg)' : undefined }}
                >
                  <img alt="" className="block size-[14px] max-w-none" src={imgIcon} />
                </span>
              </button>
            </h3>

            {/* 0fr -> 1fr expands to exactly the answer's own height, so the
                row grows to fit the copy rather than to a guessed number. */}
            <div
              className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
              style={{ gridTemplateRows: open ? '1fr' : '0fr' }}
            >
              <div className="overflow-hidden">
                <p
                  id={`faq-answer-${i}`}
                  role="region"
                  aria-labelledby={`faq-question-${i}`}
                  aria-hidden={!open}
                  className="px-[20px] pb-[18px] font-sans text-[14px] font-normal not-italic leading-[19.6px] text-[var(--ln-faq-ink-soft)]"
                >
                  {faqAnswers[i]}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
