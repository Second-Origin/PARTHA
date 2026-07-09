import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import type { ExportFormat, ExportTarget } from '@/shared/services/api/types';
import { exportService, getErrorMessage } from '@/shared/services/api';
import { downloadExport } from '@/shared/utils/downloadExport';

const ALL_FORMATS: { label: string; format: ExportFormat }[] = [
  { label: 'Markdown', format: 'markdown' },
  { label: 'HTML', format: 'html' },
  { label: 'JSON', format: 'json' },
  { label: 'PDF', format: 'pdf' },
];

interface ExportMenuProps {
  repositoryId: string;
  target: ExportTarget;
  formats?: ExportFormat[];
  disabled?: boolean;
}

export function ExportMenu({ repositoryId, target, formats, disabled = false }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const options = formats ? ALL_FORMATS.filter((option) => formats.includes(option.format)) : ALL_FORMATS;

  const handleExport = async (format: ExportFormat) => {
    setBusy(format);
    setError(null);
    try {
      const result = await exportService.export({ repositoryId, target, format });
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
        disabled={disabled}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Download className="h-3.5 w-3.5" />
        Export
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full right-0 mt-1 w-44 rounded-lg border border-border bg-popover shadow-lg z-50 p-1">
            {options.map(({ label, format }) => (
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
