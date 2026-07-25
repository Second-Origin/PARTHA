import { Info } from 'lucide-react';
import type { IntelligenceProvenance } from '@/shared/services/api/types';

interface ProvenanceNoticeProps {
  provenance: IntelligenceProvenance | null | undefined;
}

/**
 * Discloses which intelligence path produced the data on screen.
 *
 * Snapshot-backed (`ri.v1`) results render nothing: evidence-grade provenance
 * is the product's baseline promise, not a caveat. Legacy heuristic results
 * render a visible Preview notice carrying the limitation the backend
 * declared, so a user can never mistake a heuristic answer for sealed evidence.
 */
export function ProvenanceNotice({ provenance }: ProvenanceNoticeProps) {
  if (!provenance || provenance.source !== 'legacy-heuristic') return null;

  return (
    <div
      role="note"
      data-testid="provenance-notice"
      className="mb-4 flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2"
    >
      <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
      <p className="text-xs text-foreground">
        <span className="mr-1.5 rounded bg-amber-500/20 px-1.5 py-0.5 font-medium uppercase tracking-wide text-amber-600">
          Preview
        </span>
        {provenance.limitation}
      </p>
    </div>
  );
}
