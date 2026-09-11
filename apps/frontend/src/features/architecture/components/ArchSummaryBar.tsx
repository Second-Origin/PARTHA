import { Code2, Layers, Box, FileCode, Route, Cpu } from 'lucide-react';
import type { RepositorySource } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { cn } from '@/shared/utils/cn';

const NOT_ASSESSED = 'Not assessed';

interface ArchSummaryBarProps {
  model: ArchitectureModel;
  source?: RepositorySource | null;
}

export function ArchSummaryBar({ model, source }: ArchSummaryBarProps) {
  // A pattern that was not detected and an entry point that was not observed
  // are reported as such (#446). The previous placeholders -- "Repository
  // Architecture", "/" -- sat in these slots looking exactly like findings.
  const items = [
    { icon: Code2, label: 'Language', value: model.summary.language },
    { icon: Layers, label: 'Framework', value: model.summary.framework },
    { icon: Cpu, label: 'Architecture', value: model.summary.architecturePattern ?? NOT_ASSESSED },
    { icon: Box, label: 'Layers', value: String(model.detectedLayers.length) },
    { icon: Route, label: 'Modules', value: String(model.summary.totalModules) },
    {
      icon: FileCode,
      label: 'Entry',
      value: model.summary.entryPoint?.split('/').pop() || NOT_ASSESSED,
    },
  ];

  return (
    <div className="flex items-center gap-4 px-4 py-2.5 border-b border-border bg-card/50 overflow-x-auto scrollbar-thin">
      <DataSourceBadge source={source} />
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2 shrink-0">
          <item.icon className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-2xs text-muted-foreground">{item.label}:</span>
          <span
            className={cn(
              'text-2xs',
              item.value === NOT_ASSESSED ? 'italic text-muted-foreground' : 'font-medium text-foreground',
            )}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
