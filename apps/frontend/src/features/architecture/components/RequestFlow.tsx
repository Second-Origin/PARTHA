import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Monitor, Route, Waypoints, Cog, Database, Globe, ArrowDown,
  Shield, Zap, ListTodo,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { RequestFlowStep, ArchNodeType } from '@/shared/types/architecture';

const stepIcons: Partial<Record<ArchNodeType, typeof Monitor>> = {
  frontend: Monitor,
  route: Route,
  controller: Waypoints,
  service: Cog,
  'external-api': Globe,
  middleware: Shield,
  authentication: Shield,
  database: Database,
  cache: Zap,
  queue: ListTodo,
};

interface RequestFlowProps {
  steps: RequestFlowStep[];
}

export function RequestFlow({ steps }: RequestFlowProps) {
  const [selectedStep, setSelectedStep] = useState<string | null>(null);

  return (
    <div className="flex flex-col items-center py-6">
      <h2 className="text-sm font-medium text-foreground mb-6">Request Flow</h2>
      <div className="space-y-0">
        {steps.map((step, index) => {
          const Icon = stepIcons[step.type] || Cog;
          const isSelected = selectedStep === step.id;
          const isLast = index === steps.length - 1;

          return (
            <div key={step.id} className="flex flex-col items-center">
              <motion.button
                onClick={() => setSelectedStep(isSelected ? null : step.id)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={cn(
                  'relative flex items-center gap-3 rounded-xl border px-5 py-3 w-72 text-left transition-all',
                  isSelected
                    ? 'border-primary bg-primary/5 shadow-sm'
                    : 'border-border bg-card hover:border-muted-foreground/30'
                )}
              >
                <div className={cn(
                  'flex h-9 w-9 items-center justify-center rounded-lg shrink-0',
                  isSelected ? 'bg-primary/10' : 'bg-muted'
                )}>
                  <Icon className={cn('h-4 w-4', isSelected ? 'text-primary' : 'text-muted-foreground')} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className={cn('text-xs font-medium', isSelected ? 'text-foreground' : 'text-foreground')}>{step.name}</p>
                  <p className="text-2xs text-muted-foreground truncate">{step.description}</p>
                </div>
                <span className="text-2xs text-muted-foreground shrink-0">{index + 1}</span>
              </motion.button>

              {isSelected && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="w-72 mt-2 mb-2 rounded-lg border border-border bg-card p-3"
                >
                  <ul className="space-y-1">
                    {step.details.map((detail, i) => (
                      <li key={i} className="flex items-start gap-2 text-2xs text-muted-foreground">
                        <span className="text-primary mt-0.5">-</span>
                        {detail}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              )}

              {!isLast && (
                <div className="flex flex-col items-center py-1">
                  <div className="w-px h-4 bg-border" />
                  <ArrowDown className="h-3 w-3 text-muted-foreground" />
                  <div className="w-px h-4 bg-border" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
