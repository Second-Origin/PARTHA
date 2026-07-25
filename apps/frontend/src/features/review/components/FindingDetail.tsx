import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { X, AlertTriangle, FileCode, ShieldCheck, ArrowRight, Database } from 'lucide-react';
import type { ReviewFinding } from '@/shared/types/review';

interface FindingDetailProps {
  repositoryId: string;
  finding: ReviewFinding;
  onClose: () => void;
}

function evidenceHref(repositoryId: string, finding: ReviewFinding): string {
  const params = new URLSearchParams({
    tab: 'Explorer',
    path: finding.path,
    startLine: String(finding.startLine),
    endLine: String(finding.endLine),
    snapshotId: finding.snapshotId,
    factId: finding.factId,
  });
  return `/repositories/${repositoryId}?${params.toString()}`;
}

export function FindingDetail({ repositoryId, finding, onClose }: FindingDetailProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const dialog = closeRef.current?.closest<HTMLElement>('[role="dialog"]');
      const focusable = Array.from(
        dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])') ?? [],
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <>
      <button
        type="button"
        aria-label="Close finding detail"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-background/60"
      />
      <motion.aside
        role="dialog"
        aria-modal="true"
        aria-label={`Engineering finding: ${finding.title}`}
        initial={{ x: 24, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 24, opacity: 0 }}
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col overflow-hidden border-l border-border bg-card shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-medium text-foreground">{finding.title}</h2>
            <p className="text-[10px] uppercase text-muted-foreground">
              {finding.severity} · {finding.diagnosticCode}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close finding detail"
            className="rounded-md p-1 text-muted-foreground hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin">
          <Section title="Verified concern" icon={AlertTriangle}>
            <p className="text-xs leading-relaxed text-muted-foreground">{finding.explanation}</p>
          </Section>
          <Section title="Remediation guidance" icon={ArrowRight}>
            <p className="text-xs leading-relaxed text-foreground">{finding.remediationGuidance}</p>
          </Section>
          <Section title="Authentic source evidence" icon={FileCode}>
            <Link
              to={evidenceHref(repositoryId, finding)}
              className="inline-flex rounded text-xs font-mono text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              {finding.path}:{finding.startLine}
              {finding.endLine !== finding.startLine ? `-${finding.endLine}` : ''}
            </Link>
            <dl className="mt-3 space-y-2 text-[10px] text-muted-foreground">
              <Field label="Fact ID" value={finding.factId} />
              <Field label="Evidence ID" value={finding.evidenceId} />
              <Field label="Extractor" value={`${finding.extractorName}@${finding.extractorVersion}`} />
            </dl>
          </Section>
          <Section title="Snapshot provenance" icon={Database}>
            <dl className="space-y-2 text-[10px] text-muted-foreground">
              <Field label="Snapshot" value={finding.snapshotId} />
              <Field label="Rule" value={finding.ruleId} />
              <Field label="Support status" value={finding.supportStatus} />
              <Field label="Source" value={finding.provenance.source} />
            </dl>
          </Section>
          <div className="flex items-start gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            <p className="text-xs text-muted-foreground">
              This finding is shown because its fact and source span belong to the selected sealed snapshot.
            </p>
          </div>
        </div>
      </motion.aside>
    </>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof AlertTriangle;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border p-3">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        <h3 className="text-xs font-medium text-foreground">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="uppercase tracking-wide">{label}</dt>
      <dd className="break-all font-mono text-foreground">{value}</dd>
    </div>
  );
}
