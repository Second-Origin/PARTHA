import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import type { EngineeringReview } from '@/shared/types/review';
import type { ExportFormat } from '@/shared/services/api/types';
import { exportService } from '@/shared/services/api/documentation';
import { getErrorMessage } from '@/shared/services/api';
import { downloadExport } from '@/shared/utils/downloadExport';

interface ReviewExportProps {
  review: EngineeringReview;
}

const FORMATS: { label: string; format: ExportFormat }[] = [
  { label: 'Markdown', format: 'markdown' },
  { label: 'HTML', format: 'html' },
  { label: 'JSON', format: 'json' },
  { label: 'PDF', format: 'pdf' },
];

export function ReviewExport({ review }: ReviewExportProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async (format: ExportFormat) => {
    setBusy(format);
    setError(null);
    try {
      const result = await exportService.export({
        repositoryId: review.repositoryId,
        target: 'review',
        format,
      });
      downloadExport(result);
      setOpen(false);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-foreground hover:bg-accent transition-colors"
      >
        <Download className="h-3.5 w-3.5" />
        Export
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full right-0 mt-1 w-44 rounded-lg border border-border bg-popover shadow-lg z-50 p-1">
            {FORMATS.map(({ label, format }) => (
              <button
                key={format}
                onClick={() => handleExport(format)}
                disabled={busy !== null}
                className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {label}
                {busy === format && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              </button>
            ))}
            {error && <p className="px-3 py-1.5 text-[11px] text-destructive">{error}</p>}
          </div>
        </>
      )}
    </div>
  );
}
