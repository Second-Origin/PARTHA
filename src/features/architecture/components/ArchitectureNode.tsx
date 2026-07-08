import { memo } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import {
  Monitor, Server, Waypoints, Route, Cog, Database, Settings,
  Shield, Layers, Wrench, Box, Globe, Library, CloudCog,
  ListTodo, Zap,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import type { ArchNodeType } from '@/types/architecture';

const nodeConfig: Record<ArchNodeType, { icon: typeof Monitor; color: string; bg: string }> = {
  frontend: { icon: Monitor, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30' },
  backend: { icon: Server, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30' },
  controller: { icon: Waypoints, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  route: { icon: Route, color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500/30' },
  service: { icon: Cog, color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/30' },
  repository: { icon: Database, color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/30' },
  database: { icon: Database, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30' },
  configuration: { icon: Settings, color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/30' },
  authentication: { icon: Shield, color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  middleware: { icon: Layers, color: 'text-teal-400', bg: 'bg-teal-500/10 border-teal-500/30' },
  utilities: { icon: Wrench, color: 'text-zinc-400', bg: 'bg-zinc-500/10 border-zinc-500/30' },
  models: { icon: Box, color: 'text-pink-400', bg: 'bg-pink-500/10 border-pink-500/30' },
  'external-api': { icon: Globe, color: 'text-sky-400', bg: 'bg-sky-500/10 border-sky-500/30' },
  'shared-library': { icon: Library, color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/30' },
  environment: { icon: CloudCog, color: 'text-gray-400', bg: 'bg-gray-500/10 border-gray-500/30' },
  queue: { icon: ListTodo, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30' },
  cache: { icon: Zap, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
};

export interface ArchNodeData {
  label: string;
  nodeType: ArchNodeType;
  description: string;
  filesCount: number;
  complexity: 'low' | 'medium' | 'high';
  isSelected?: boolean;
  isHighlighted?: boolean;
  heatmapIntensity?: number;
  isBookmarked?: boolean;
  [key: string]: unknown;
}

export type ArchFlowNode = Node<ArchNodeData, 'architectureNode'>;

export const ArchitectureNode = memo(({ data }: NodeProps<ArchFlowNode>) => {
  const config = nodeConfig[data.nodeType] || nodeConfig.utilities;
  const Icon = config.icon;
  const heatIntensity = data.heatmapIntensity ?? 0;

  const heatmapBorder = heatIntensity > 0
    ? heatIntensity > 0.7
      ? 'ring-2 ring-red-500/60'
      : heatIntensity > 0.4
        ? 'ring-2 ring-amber-500/50'
        : 'ring-1 ring-yellow-500/30'
    : '';

  return (
    <div
      className={cn(
        'relative rounded-lg border px-4 py-3 min-w-[160px] max-w-[200px] shadow-sm transition-all duration-200',
        config.bg,
        data.isSelected && 'ring-2 ring-primary shadow-lg scale-105',
        data.isHighlighted && !data.isSelected && 'ring-1 ring-primary/50 shadow-md',
        heatmapBorder && !data.isSelected && heatmapBorder,
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-muted-foreground/50 !border-0"
      />
      <div className="flex items-start gap-2.5">
        <div className={cn('mt-0.5 shrink-0', config.color)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1">
            <p className="text-xs font-medium text-foreground truncate">{data.label}</p>
            {data.isBookmarked && (
              <span className="text-amber-400 text-[10px]">*</span>
            )}
          </div>
          <p className="text-2xs text-muted-foreground mt-0.5 line-clamp-1">{data.description}</p>
          <div className="flex items-center gap-2 mt-1.5">
            {data.filesCount > 0 && (
              <span className="text-2xs text-muted-foreground">{data.filesCount} files</span>
            )}
            <span
              className={cn(
                'text-2xs px-1 py-0.5 rounded',
                data.complexity === 'high' && 'bg-destructive/10 text-destructive',
                data.complexity === 'medium' && 'bg-warning/10 text-warning',
                data.complexity === 'low' && 'bg-success/10 text-success'
              )}
            >
              {data.complexity}
            </span>
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-muted-foreground/50 !border-0"
      />
    </div>
  );
});

ArchitectureNode.displayName = 'ArchitectureNode';
