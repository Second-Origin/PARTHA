import { Flag, Clock } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { ImprovementStep } from '@/types/review';

interface RoadmapProps {
  steps: ImprovementStep[];
}

export function Roadmap({ steps }: RoadmapProps) {
  if (steps.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="text-sm font-medium text-foreground mb-4 flex items-center gap-2">
        <Flag className="h-4 w-4 text-muted-foreground" />
        Improvement Roadmap
      </h3>
      <div className="space-y-4">
        {steps.map((step, idx) => {
          const priorityColor = {
            critical: 'border-red-500/30 bg-red-500/5',
            high: 'border-orange-500/30 bg-orange-500/5',
            medium: 'border-amber-500/30 bg-amber-500/5',
            low: 'border-blue-500/30 bg-blue-500/5',
          }[step.priority];

          return (
            <div key={step.id} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className={cn(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold',
                  priorityColor
                )}>
                  {idx + 1}
                </div>
                {idx < steps.length - 1 && (
                  <div className="w-px flex-1 bg-border mt-1" />
                )}
              </div>
              <div className={cn('flex-1 rounded-lg border p-3 mb-2', priorityColor)}>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs font-medium text-foreground">{step.title}</p>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {step.estimatedEffort}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{step.description}</p>
                {step.relatedFindings.length > 0 && (
                  <p className="text-[10px] text-muted-foreground mt-2">
                    {step.relatedFindings.length} related findings
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
