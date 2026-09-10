import { HOW_IT_WORKS } from '@/data/landing';
import { cn } from '@/utils/cn';

/** Step surface colours, sampled from the design frame. The fourth step is the
 * saturated one, so its text inverts. */
const TONE = {
  blue: 'bg-[var(--ln-blue)] text-[var(--ln-ink)]',
  grey: 'bg-[var(--ln-grey)] text-[var(--ln-ink)]',
  sand: 'bg-[var(--ln-sand)] text-[var(--ln-ink)]',
  orange: 'bg-[var(--ln-orange)] text-[var(--ln-ink)]',
} as const;

/** "From code to clarity": the four-step pipeline, one column per step. */
export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-[var(--ln-page)] pb-[80px] pt-[40px] lg:pb-[120px] lg:pt-[56px]">
      <div className="mx-auto w-full max-w-[1568px] px-6 lg:px-10">
        <header className="text-center">
          <p className="font-display text-[20px] font-extralight text-[var(--ln-ink-soft)] lg:text-[27px]">
            {HOW_IT_WORKS.eyebrow}
          </p>
          <h2 className="mt-1 font-display text-[32px] font-light leading-[1.15] text-[var(--ln-ink)] lg:text-[46px]">
            {HOW_IT_WORKS.heading}
          </h2>
        </header>

        <ol className="mt-[44px] grid gap-6 lg:mt-[62px] lg:grid-cols-4 lg:gap-[26px]">
          {HOW_IT_WORKS.steps.map((step, index) => (
            <li
              key={step.heading}
              className={cn(
                'flex flex-col rounded-[24px] p-7 lg:rounded-[14px] lg:p-8',
                TONE[step.tone],
              )}
            >
              <p className="font-sans text-[14px] capitalize leading-none text-[var(--ln-ink-soft)] lg:text-[16px]">
                <span className="sr-only">{`Step ${index + 1}: `}</span>
                {step.kicker}
              </p>
              <h3 className="mt-3 font-accent text-[24px] capitalize leading-[1.2] lg:mt-4 lg:text-[30px]">
                {step.heading}
              </h3>

              <div className="my-7 flex flex-1 items-center justify-center lg:my-9">
                <img
                  src={step.image}
                  alt={step.alt}
                  loading="lazy"
                  className="max-h-[230px] w-full max-w-[280px] object-contain"
                />
              </div>

              <p className="font-sans text-[14px] leading-[1.5] text-[var(--ln-ink-soft)] lg:text-[15px]">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
