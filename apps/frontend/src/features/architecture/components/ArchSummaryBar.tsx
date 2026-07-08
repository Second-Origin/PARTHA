import { Code2, Layers, Box, FileCode, Route, Cpu } from 'lucide-react';
import type { DataSource } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';

interface ArchSummaryBarProps {
  model: ArchitectureModel;
  source?: DataSource | null;
}

export function ArchSummaryBar({ model, source }: ArchSummaryBarProps) {
  const items = [
    { icon: Code2, label: 'Language', value: model.summary.language },
    { icon: Layers, label: 'Framework', value: model.summary.framework },
    { icon: Cpu, label: 'Architecture', value: model.summary.architecturePattern },
    { icon: Box, label: 'Layers', value: String(model.detectedLayers.length) },
    { icon: Route, label: 'Modules', value: String(model.summary.totalModules) },
    { icon: FileCode, label: 'Entry', value: model.summary.entryPoint.split('/').pop() || '' },
  ];

  return (
    <div className="flex items-center gap-4 px-4 py-2.5 border-b border-border bg-card/50 overflow-x-auto scrollbar-thin">
      <DataSourceBadge source={source} />
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2 shrink-0">
          <item.icon className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-2xs text-muted-foreground">{item.label}:</span>
          <span className="text-2xs font-medium text-foreground">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
