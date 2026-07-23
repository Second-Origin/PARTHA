import { AnimatePresence, motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, X, ShieldCheck, ChevronRight } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { AuthClaim, AuthClaimKind, AuthEvidenceRef, AuthRelationshipNodeKind } from '@/shared/services/api/types';
import { useAuthenticationExplanation } from '../hooks/useAuthenticationExplanation';

interface AuthenticationExplanationPanelProps {
  open: boolean;
  onClose: () => void;
}

const GROUP_ORDER: Array<{ kind: AuthClaimKind; label: string }> = [
  { kind: 'route', label: 'Routes' },
  { kind: 'middleware', label: 'Middleware & guards' },
  { kind: 'service', label: 'Services' },
  { kind: 'model', label: 'Models' },
  { kind: 'dependency', label: 'Dependencies' },
];

const ROLE_LABEL: Record<AuthRelationshipNodeKind, string> = {
  route: 'route',
  handler: 'handler',
  middleware: 'guard',
  service: 'service',
  model: 'model',
  dependency: 'dependency',
};

function evidenceHref(repositoryId: string, evidence: AuthEvidenceRef): string {
  const params = new URLSearchParams({
    tab: 'Explorer',
    path: evidence.path,
    startLine: String(evidence.startLine),
    endLine: String(evidence.endLine),
    snapshotId: evidence.snapshotId,
    factId: evidence.factId,
  });
  return `/repositories/${repositoryId}?${params.toString()}`;
}

function EvidenceCitation({ repositoryId, evidence }: { repositoryId: string; evidence: AuthEvidenceRef }) {
  const span = evidence.startLine === evidence.endLine ? `${evidence.startLine}` : `${evidence.startLine}-${evidence.endLine}`;
  const label = `View evidence at ${evidence.path}, line ${span}`;

  return (
    <Link
      to={evidenceHref(repositoryId, evidence)}
      aria-label={label}
      className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary rounded-sm"
    >
      {evidence.path}:{span}
    </Link>
  );
}

function ClaimRow({ claim, repositoryId }: { claim: AuthClaim; repositoryId: string }) {
  return (
    <li className="rounded-md border border-border px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground truncate">{claim.name}</span>
        <span
          className={cn(
            'text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0',
            claim.confidence === 'observed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400',
          )}
        >
          {claim.confidence === 'observed' ? 'observed' : 'inferred'}
        </span>
      </div>
      <div className="mt-1 flex flex-col gap-0.5">
        {claim.evidence.map((item, index) => (
          <EvidenceCitation key={`${item.factId}-${index}`} repositoryId={repositoryId} evidence={item} />
        ))}
      </div>
    </li>
  );
}

export function AuthenticationExplanationPanel({ open, onClose }: AuthenticationExplanationPanelProps) {
  const { explanation, loading, error, status, retry } = useAuthenticationExplanation(open);

  const claimsByKind = new Map<AuthClaimKind, AuthClaim[]>();
  for (const claim of explanation?.claims ?? []) {
    const bucket = claimsByKind.get(claim.kind) ?? [];
    bucket.push(claim);
    claimsByKind.set(claim.kind, bucket);
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-background/60"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Authentication explanation"
            initial={{ x: 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 24, opacity: 0 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md border-l border-border bg-card shadow-xl flex flex-col"
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-medium text-foreground">Authentication explanation</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close authentication explanation"
                className="rounded-md p-1 text-muted-foreground hover:bg-accent/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-3">
              {loading && (
                <div className="flex flex-col items-center gap-2 py-10">
                  <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                  <span className="text-xs text-muted-foreground">Loading authentication explanation...</span>
                </div>
              )}

              {!loading && error && (
                <div className="text-center py-10">
                  <p className="text-sm text-destructive mb-2">{error}</p>
                  <button onClick={retry} className="text-xs text-primary hover:underline">
                    Retry
                  </button>
                </div>
              )}

              {!loading && !error && status === 'empty' && (
                <p className="text-xs text-muted-foreground py-10 text-center">
                  Select an analysed repository to see how authentication works.
                </p>
              )}

              {!loading && !error && explanation && explanation.status === 'missing_snapshot' && (
                <p className="text-xs text-muted-foreground py-10 text-center">{explanation.summary}</p>
              )}

              {!loading && !error && explanation && explanation.status === 'ready' && (
                <div className="space-y-5">
                  <p className="text-xs text-muted-foreground">{explanation.summary}</p>

                  {explanation.chains.length > 0 && (
                    <div>
                      <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                        <ChevronRight className="h-3 w-3" />
                        How authentication works
                      </h3>
                      <ul className="space-y-3">
                        {explanation.chains.map((chain) => (
                          <li key={chain.route} className="rounded-md border border-border p-2.5">
                            <p className="text-xs font-medium text-foreground mb-2">{chain.route}</p>
                            <ol className="space-y-1.5">
                              {chain.hops.map((hop, index) => (
                                <li key={`${chain.route}-${index}`} className="flex flex-col gap-0.5">
                                  <div className="flex items-center gap-1.5 text-[11px] text-foreground flex-wrap">
                                    <span className="font-mono">{hop.subject}</span>
                                    <span className="text-muted-foreground">({ROLE_LABEL[hop.subjectKind]})</span>
                                    <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                                    <span className="font-mono">{hop.object}</span>
                                    <span className="text-muted-foreground">({ROLE_LABEL[hop.objectKind]})</span>
                                    <span className="text-[10px] text-muted-foreground/70">{hop.predicate}</span>
                                  </div>
                                  {hop.evidence.map((item, evidenceIndex) => (
                                    <EvidenceCitation
                                      key={`${item.factId}-${evidenceIndex}`}
                                      repositoryId={explanation.repositoryId}
                                      evidence={item}
                                    />
                                  ))}
                                </li>
                              ))}
                            </ol>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {GROUP_ORDER.map(({ kind, label }) => {
                    const claims = claimsByKind.get(kind);
                    if (!claims || claims.length === 0) return null;
                    return (
                      <div key={kind}>
                        <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-1.5 flex items-center gap-1">
                          <ChevronRight className="h-3 w-3" />
                          {label}
                        </h3>
                        <ul className="space-y-1.5">
                          {claims.map((claim, index) => (
                            <ClaimRow
                              key={`${claim.kind}-${claim.name}-${index}`}
                              claim={claim}
                              repositoryId={explanation.repositoryId}
                            />
                          ))}
                        </ul>
                      </div>
                    );
                  })}

                  {explanation.claims.length === 0 && (
                    <p className="text-xs text-muted-foreground py-6 text-center">
                      No authentication-relevant routes, middleware, services, or models were found in this
                      repository's analysed snapshot.
                    </p>
                  )}

                  {explanation.diagnostics.length > 0 && (
                    <div>
                      <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
                        Gaps and unresolved facts
                      </h3>
                      <ul className="space-y-1">
                        {explanation.diagnostics.map((diagnostic, index) => (
                          <li key={`${diagnostic.code}-${index}`} className="text-[10px] text-amber-400">
                            {diagnostic.message}
                            {diagnostic.path && ` (${diagnostic.path}${diagnostic.startLine ? `:${diagnostic.startLine}` : ''})`}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
