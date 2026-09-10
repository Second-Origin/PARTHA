import { MEET, STORY_CARDS } from '@/data/landing';
import { cn } from '@/utils/cn';

/** Surface colours sampled from the design frame. */
const TONE = {
  blue: 'bg-[var(--ln-blue)]',
  peach: 'bg-[var(--ln-peach)]',
} as const;

type Card = (typeof STORY_CARDS)[number];

/** Splits a heading around the design's highlighted word so it can be tinted
 * without hard-coding the copy into the markup. */
function Heading({ card }: { card: Card }) {
  const highlight = 'highlight' in card ? card.highlight : undefined;
  if (!highlight) return <>{card.heading}</>;

  const [before, ...rest] = card.heading.split(highlight);
  return (
    <>
      {before}
      <span className="text-primary">{highlight}</span>
      {rest.join(highlight)}
    </>
  );
}

function StoryCard({ card, className }: { card: Card; className?: string }) {
  return (
    <article
      className={cn(
        'relative flex h-full flex-col gap-8 overflow-hidden rounded-[40px] p-8 sm:p-10 lg:flex-row lg:items-center lg:gap-6 lg:rounded-[52px] lg:p-[52px]',
        TONE[card.tone],
        className,
      )}
    >
      <div className="flex flex-col lg:max-w-[46%]">
        <p className="font-display text-[12px] font-medium uppercase tracking-[0.13em] text-[var(--ln-eyebrow)] lg:text-[15px]">
          {card.eyebrow}
        </p>
        <h3 className="mt-3 font-display text-[30px] font-light capitalize leading-[1.1] tracking-[-0.015em] text-[var(--ln-ink)] lg:mt-4 lg:text-[46px]">
          <Heading card={card} />
        </h3>
        <p className="mt-5 max-w-[38ch] font-sans text-[15px] leading-[1.5] text-[var(--ln-ink-soft)] lg:mt-7 lg:text-[17px]">
          {card.body}
        </p>
      </div>

      <img
        src={card.image}
        alt={card.alt}
        loading="lazy"
        className="mx-auto w-full max-w-[320px] self-center lg:mx-0 lg:ml-auto lg:max-w-[46%]"
      />
    </article>
  );
}

/** "Meet Partha" plus the four interlocking product cards.
 *
 * The design nests the two peach cards inside a paler peach surround so the
 * four tiles read as one interlocking pinwheel rather than a plain grid. That
 * surround is the `p-*` wrapper below; it collapses on small screens where the
 * cards stack. */
export function StoryCards() {
  return (
    <section id="product" className="bg-[var(--ln-page)] pb-[80px] pt-[70px] lg:pb-[130px] lg:pt-[104px]">
      <div className="mx-auto w-full max-w-[1568px] px-6 lg:px-10">
        <header className="text-center">
          <h2 className="font-accent text-[40px] leading-[1.1] text-[var(--ln-ink)] lg:text-[62px]">
            {MEET.lead} <em className="not-italic text-primary">{MEET.brand}</em>
          </h2>
          <p className="mt-2 font-accent text-[20px] text-[var(--ln-ink-muted)] lg:text-[26px]">{MEET.sub}</p>
        </header>

        <div className="mt-[46px] grid gap-6 lg:mt-[64px] lg:grid-cols-2 lg:gap-0">
          {/* Top-left: sits flush, the pinwheel's leading tile. */}
          <StoryCard card={STORY_CARDS[0]} className="lg:mr-4" />

          {/* Top-right: paler peach surround wraps down and to the left. */}
          <div className="rounded-[40px] bg-[var(--ln-peach-soft)] lg:rounded-[64px] lg:pb-10 lg:pl-10 lg:pt-6">
            <StoryCard card={STORY_CARDS[1]} />
          </div>

          {/* Bottom-left: the mirrored surround, wrapping up and to the right. */}
          <div className="rounded-[40px] bg-[var(--ln-peach-soft)] lg:-mt-10 lg:rounded-[64px] lg:pb-6 lg:pr-10 lg:pt-10">
            <StoryCard card={STORY_CARDS[2]} />
          </div>

          {/* Bottom-right: flush again, closing the pinwheel. */}
          <StoryCard card={STORY_CARDS[3]} className="lg:ml-4 lg:mt-4" />
        </div>
      </div>
    </section>
  );
}
