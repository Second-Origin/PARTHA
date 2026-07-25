import { Info } from 'lucide-react';

interface PreviewBannerProps {
  /** User-facing statement of what is limited about this surface. */
  limitation: string;
}

/**
 * Marks a surface that works and shows only real repository data, but is
 * limited in a way the user must know before trusting it.
 *
 * Every `preview` surface in the product-surface registry renders this, so a
 * limited surface can never be mistaken for a fully verified one.
 */
export function PreviewBanner({ limitation }: PreviewBannerProps) {
  return (
    <div
      role="note"
      data-testid="preview-banner"
      className="mb-4 flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2"
    >
      <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
      <p className="text-xs text-foreground">
        <span className="mr-1.5 rounded bg-amber-500/20 px-1.5 py-0.5 font-medium uppercase tracking-wide text-amber-600">
          Preview
        </span>
        {limitation}
      </p>
    </div>
  );
}
