import externalLinkIcon from '@/assets/landing/figma/external-link.png';
import heroGlow from '@/assets/landing/hero-glow.svg';
import playIcon from '@/assets/landing/figma/line-md-play-filled.svg';
import { HERO } from '@/data/landing';

type Props = {
  onAnalyze: () => void;
  onSeeHowItWorks: () => void;
};

/** Opening statement: eyebrow pill, the two-line display headline, the body
 * paragraph, both calls to action, and the qualifying footnote.
 *
 * The design floats a warm glow behind the left of the headline and a cool one
 * to the right; both are decorative and hidden from assistive technology. */
export function Hero({ onAnalyze, onSeeHowItWorks }: Props) {
  return (
    <section id="top" className="relative overflow-hidden bg-[var(--ln-page)]">
      {/* Decorative field: warm glow left, cool wash right. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <img
          src={heroGlow}
          alt=""
          className="absolute -left-[22%] top-[6%] w-[70%] max-w-[1014px] opacity-90"
        />
        <div className="absolute -right-[10%] top-0 h-full w-[55%] bg-[radial-gradient(60%_55%_at_70%_35%,rgba(0,98,152,0.10)_0%,rgba(0,98,152,0)_70%)]" />
      </div>

      <div className="relative mx-auto flex w-full max-w-[1568px] flex-col items-center px-6 pb-[92px] pt-[72px] text-center lg:px-10 lg:pb-[140px] lg:pt-[104px]">
        <p className="inline-flex items-center gap-[10px] rounded-full border border-primary/60 px-[18px] py-[7px] font-display text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--ln-hero-head)] lg:text-[13px]">
          <span aria-hidden className="size-[7px] rounded-full bg-primary" />
          {HERO.eyebrow}
        </p>

        <h1 className="mt-[38px] max-w-[15ch] font-display text-[44px] font-extrabold capitalize leading-[1.06] tracking-[-0.02em] text-[var(--ln-hero-head)] sm:text-[62px] lg:text-[86px] lg:leading-[1.08]">
          {HERO.headingLine1}
          <br />
          {HERO.headingLine2}
          <br />
          {HERO.headingLine3}
        </h1>

        <p className="mt-[26px] max-w-[62ch] font-accent text-[19px] leading-[1.45] text-[var(--ln-ink-soft)] lg:text-[24px]">
          {HERO.body}
        </p>

        <div className="mt-[40px] flex w-full flex-col items-center gap-[18px] sm:w-auto sm:flex-row sm:gap-[44px]">
          <button
            type="button"
            onClick={onSeeHowItWorks}
            className="inline-flex w-full items-center justify-center gap-[12px] rounded-[12px] border-[1.5px] border-[var(--ln-blue-ink)] bg-[var(--ln-card)] px-[30px] py-[15px] font-display text-[17px] font-semibold text-[var(--ln-blue-ink)] transition-colors hover:bg-[#006298] hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ln-blue-ink)] sm:w-auto lg:text-[19px]"
          >
            {HERO.secondaryCta}
            <span aria-hidden className="size-[18px] shrink-0 overflow-clip">
              <img src={playIcon} alt="" className="size-full object-contain" />
            </span>
          </button>
          <button
            type="button"
            onClick={onAnalyze}
            className="inline-flex w-full items-center justify-center gap-[12px] rounded-[12px] bg-primary px-[30px] py-[15px] font-display text-[17px] font-semibold text-white transition-colors hover:bg-[#d94301] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:w-auto lg:text-[19px]"
          >
            {HERO.primaryCta}
            <span aria-hidden className="size-[19px] shrink-0 overflow-clip">
              <img src={externalLinkIcon} alt="" className="size-full object-contain" />
            </span>
          </button>
        </div>

        <p className="mt-[34px] font-display text-[12px] font-medium uppercase tracking-[0.10em] text-[var(--ln-ink-muted)] lg:text-[15px]">
          {HERO.footnote}
        </p>
      </div>
    </section>
  );
}
