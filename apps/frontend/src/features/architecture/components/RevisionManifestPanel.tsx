import { useCallback, useEffect, useState } from 'react';
import { Check, Copy, Download, ShieldCheck } from 'lucide-react';
import { architectureService } from '@/shared/services/api/architecture';
import { getErrorMessage } from '@/shared/services/api';
import type { RevisionManifestResponse } from '@/shared/services/api/types';

interface RevisionManifestPanelProps {
  repositoryId: string;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="truncate font-mono text-xs text-foreground" title={value}>
        {value}
      </dd>
    </div>
  );
}

/**
 * Shows the verifiable identity of the snapshot the surrounding evidence was
 * derived from, and lets the user take it away (#113).
 *
 * The exported JSON is the exact response body, so it can be replayed against
 * the verify endpoint later. The digest is a canonical content hash: the panel
 * states that plainly rather than implying the manifest is signed.
 */
export function RevisionManifestPanel({ repositoryId }: RevisionManifestPanelProps) {
  const [manifest, setManifest] = useState<RevisionManifestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    architectureService
      .getRevisionManifest(repositoryId)
      .then((response) => {
        if (!cancelled) setManifest(response);
      })
      .catch((caught) => {
        if (!cancelled) setError(getErrorMessage(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [repositoryId]);

  const serialized = manifest ? JSON.stringify(manifest, null, 2) : '';

  const handleCopy = useCallback(async () => {
    if (!serialized) return;
    await navigator.clipboard.writeText(serialized);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [serialized]);

  const handleDownload = useCallback(() => {
    if (!manifest) return;
    const blob = new Blob([serialized], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `partha-revision-manifest-${manifest.manifest.snapshotId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [manifest, serialized]);

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-xs text-muted-foreground">
        Loading revision manifest...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs text-muted-foreground">
          No revision manifest is available for this repository yet. {error}
        </p>
      </div>
    );
  }

  if (!manifest) return null;

  const { manifest: body, manifestDigest, verificationState, verificationNote } = manifest;

  return (
    <section
      aria-label="Revision manifest"
      data-testid="revision-manifest"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck aria-hidden="true" className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-medium text-foreground">Revision manifest</h2>
          <span
            className="rounded bg-muted px-1.5 py-0.5 text-2xs uppercase tracking-wide text-muted-foreground"
            data-testid="verification-state"
          >
            {verificationState}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-foreground hover:bg-muted"
          >
            {copied ? <Check aria-hidden="true" className="h-3 w-3" /> : <Copy aria-hidden="true" className="h-3 w-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-foreground hover:bg-muted"
          >
            <Download aria-hidden="true" className="h-3 w-3" />
            Export
          </button>
        </div>
      </header>

      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label={body.revisionKind === 'git' ? 'Commit' : 'Content hash'} value={body.revisionValue} />
        <Field label="Snapshot" value={body.snapshotId} />
        <Field label="Snapshot schema" value={body.snapshotSchemaVersion} />
        <Field label="Canonical graph hash" value={body.canonicalGraphHash ?? 'not sealed'} />
        <Field label="Sealed at" value={body.sealedAt ?? 'not sealed'} />
        <Field label="Manifest digest" value={manifestDigest} />
      </dl>

      <div className="mt-3">
        <p className="text-2xs uppercase tracking-wide text-muted-foreground">Extractors</p>
        <ul className="mt-1 flex flex-wrap gap-1.5">
          {body.extractors.map((extractor) => (
            <li
              key={`${extractor.name}@${extractor.version}`}
              className="rounded bg-muted px-1.5 py-0.5 font-mono text-2xs text-foreground"
            >
              {extractor.name}@{extractor.version}
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-3 text-2xs text-muted-foreground">{verificationNote}</p>
    </section>
  );
}
