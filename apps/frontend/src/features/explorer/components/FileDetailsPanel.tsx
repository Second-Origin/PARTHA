import {
  FileCode, Hash, Globe, HardDrive, FolderTree,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { formatFileSize } from '@/shared/utils/cn';
import type { FileDetails } from '../fileUtils';

interface FileDetailsPanelProps {
  details: FileDetails;
}

export function FileDetailsPanel({ details }: FileDetailsPanelProps) {
  return (
    <div className="space-y-4 p-4 overflow-y-auto scrollbar-thin h-full">
      <div className="space-y-3">
        <DetailSection title="File Info">
          <DetailRow icon={FileCode} label="Name" value={details.name} />
          <DetailRow icon={FolderTree} label="Path" value={details.path} mono />
          {details.extension && (
            <DetailRow icon={Hash} label="Extension" value={`.${details.extension}`} />
          )}
          {details.language && (
            <DetailRow icon={Globe} label="Language" value={details.language} />
          )}
          <DetailRow icon={HardDrive} label="Est. Size" value={formatFileSize(details.estimatedSize)} />
        </DetailSection>

        {details.imports.length > 0 && (
          <DetailSection title="Imports">
            <div className="flex flex-wrap gap-1.5">
              {details.imports.map((imp, i) => (
                <Badge key={i} variant="import">{imp}</Badge>
              ))}
            </div>
          </DetailSection>
        )}

        {details.exports.length > 0 && (
          <DetailSection title="Exports">
            <div className="flex flex-wrap gap-1.5">
              {details.exports.map((exp, i) => (
                <Badge key={i} variant="export">{exp}</Badge>
              ))}
            </div>
          </DetailSection>
        )}

        {details.relatedModules.length > 0 && (
          <DetailSection title="Related Modules">
            <div className="flex flex-wrap gap-1.5">
              {details.relatedModules.map((mod, i) => (
                <Badge key={i} variant="module">{mod}</Badge>
              ))}
            </div>
          </DetailSection>
        )}

        {details.dependencies.length > 0 && (
          <DetailSection title="Dependencies">
            <div className="flex flex-wrap gap-1.5">
              {details.dependencies.map((dep, i) => (
                <Badge key={i} variant="dep">{dep}</Badge>
              ))}
            </div>
          </DetailSection>
        )}
      </div>
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2.5">{title}</h4>
      {children}
    </div>
  );
}

function DetailRow({
  icon: Icon, label, value, mono,
}: {
  icon: typeof FileCode; label: string; value: string; mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <span className={cn('text-xs text-foreground max-w-[60%] truncate text-right', mono && 'font-mono text-[11px]')}>
        {value}
      </span>
    </div>
  );
}

function Badge({ children, variant }: { children: React.ReactNode; variant: 'import' | 'export' | 'module' | 'dep' }) {
  const styles = {
    import: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    export: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    module: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    dep: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  };

  return (
    <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium', styles[variant])}>
      {children}
    </span>
  );
}
