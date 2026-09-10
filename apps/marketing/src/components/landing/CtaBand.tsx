import externalLinkIcon from '@/assets/landing/figma/external-link.png';
import { CTA } from '@/data/landing';

type Props = {
  onAnalyze: () => void;
};

/** Closing call to action: the private-preview statement and the two actions. */
export function CtaBand({ onAnalyze }: Props) {
  return (
    <section className="bg-[var(--ln-page)] pb-[80px] lg:pb-[110px]">
      <div className="mx-auto w-full max-w-[1568px] px-6 lg:px-10">
        <div className="rounded-[26px] border border-primary bg-[var(--ln-peach-soft)] px-6 py-[52px] text-center lg:px-16 lg:py-[70px]">
          <h2 className="mx-auto max-w-[20ch] font-display text-[30px] font-light leading-[1.2] text-[var(--ln-ink)] lg:text-[45px]">
            {CTA.heading}
          </h2>
          <p className="mx-auto mt-6 max-w-[68ch] font-accent text-[17px] leading-[1.5] text-[var(--ln-ink-soft)] lg:text-[21px]">
            {CTA.body}
          </p>

          <div className="mt-[36px] flex flex-col items-center justify-center gap-4 sm:flex-row sm:gap-[26px]">
            <button
              type="button"
              onClick={onAnalyze}
              className="inline-flex w-full items-center justify-center gap-3 rounded-full bg-primary px-[26px] py-[13px] font-display text-[15px] font-semibold text-white transition-colors hover:bg-[#d94301] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:w-auto lg:text-[17px]"
            >
              {CTA.primary}
              <span aria-hidden className="size-[17px] shrink-0 overflow-clip">
                <img src={externalLinkIcon} alt="" className="size-full object-contain" />
              </span>
            </button>

            <a
              href="https://discord.gg/qvk9DcxDA"
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-full items-center justify-center rounded-full border border-primary/70 bg-[var(--ln-card)] px-[26px] py-[13px] font-display text-[15px] font-semibold text-[var(--ln-ink)] transition-colors hover:bg-primary hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:w-auto lg:text-[17px]"
            >
              {CTA.secondary}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
