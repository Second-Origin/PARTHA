import { Flame, Activity, HardDrive, AlertTriangle } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useArchitectureStore } from '../store';
import type { HeatmapMode } from '@/shared/types/architecture';

const modes: { id: HeatmapMode; label: string; icon: typeof Flame }[] = [
  { id: 'none', label: 'Off', icon: Activity },
  { id: 'complexity', label: 'Complexity', icon: Flame },
  { id: 'usage', label: 'Usage', icon: Activity },
  { id: 'size', label: 'Size', icon: HardDrive },
  { id: 'critical', label: 'Critical', icon: AlertTriangle },
];

export function HeatmapControls() {
  const { heatmapMode, setHeatmapMode } = useArchitectureStore();

  return (
    <div className="flex items-center gap-1">
      {modes.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => setHeatmapMode(id)}
          title={`Heatmap: ${label}`}
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors',
            heatmapMode === id
              ? 'bg-accent text-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
          )}
        >
          <Icon className="h-3 w-3" />
          {label}
        </button>
      ))}
    </div>
  );
}
