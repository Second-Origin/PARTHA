import { motion } from 'framer-motion';
import {
  X, AlertTriangle, FileCode, Box, Tag, Zap, ArrowRight, Brain,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { ReviewFinding } from '@/shared/types/review';

interface FindingDetailProps {
  finding: ReviewFinding;
  onClose: () => void;
}

export function FindingDetail({ finding, onClose }: FindingDetailProps) {
  const severityColor = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-amber-400',
    low: 'text-blue-400',
  }[finding.severity];

  return (
    <motion.div
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 20, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="w-96 border-l border-border bg-card flex flex-col h-full overflow-hidden"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-foreground truncate">{finding.title}</h3>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={cn('text-[10px] font-medium capitalize', severityColor)}>{finding.severity}</span>
            <span className="text-[10px] text-muted-foreground capitalize">{finding.category.replace('-', ' ')}</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors shrink-0"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
        <Section title="Problem" icon={AlertTriangle}>
          <p className="text-xs text-muted-foreground leading-relaxed">{finding.problem}</p>
        </Section>

        <Section title="Impact" icon={Zap}>
          <p className="text-xs text-muted-foreground leading-relaxed">{finding.impact}</p>
        </Section>

        <Section title="Recommendation" icon={ArrowRight}>
          <p className="text-xs text-foreground leading-relaxed">{finding.recommendation}</p>
        </Section>

        <Section title="Metadata" icon={Tag}>
          <div className="grid grid-cols-2 gap-2">
            <MetaItem label="Priority" value={`#${finding.priority}`} />
            <MetaItem label="Effort" value={finding.estimatedEffort} />
            <MetaItem label="Status" value={finding.status} />
            <MetaItem label="Category" value={finding.category.replace('-', ' ')} />
          </div>
        </Section>

        {finding.affectedFiles.length > 0 && (
          <Section title="Affected Files" icon={FileCode}>
            <ul className="space-y-1">
              {finding.affectedFiles.map((file) => (
                <li key={file} className="text-xs text-muted-foreground font-mono">{file}</li>
              ))}
            </ul>
          </Section>
        )}

        {finding.affectedModules.length > 0 && (
          <Section title="Affected Modules" icon={Box}>
            <div className="flex flex-wrap gap-1.5">
              {finding.affectedModules.map((mod) => (
                <span key={mod} className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground capitalize">
                  {mod}
                </span>
              ))}
            </div>
          </Section>
        )}

        {finding.tags.length > 0 && (
          <Section title="Tags" icon={Tag}>
            <div className="flex flex-wrap gap-1.5">
              {finding.tags.map((tag) => (
                <span key={tag} className="text-[11px] px-2 py-0.5 rounded-md bg-primary/10 text-primary">
                  {tag}
                </span>
              ))}
            </div>
          </Section>
        )}

        <Section title="AI Analysis" icon={Brain}>
          <div className="rounded-lg bg-muted/50 border border-border p-3">
            <p className="text-xs text-muted-foreground italic">
              AI-powered analysis will provide detailed context, root cause analysis, and automated fix suggestions.
            </p>
          </div>
        </Section>
      </div>
    </motion.div>
  );
}

function Section({ title, icon: Icon, children }: { title: string; icon: typeof AlertTriangle; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        <h4 className="text-xs font-medium text-foreground">{title}</h4>
      </div>
      {children}
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/50 px-2.5 py-1.5">
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className="text-xs font-medium text-foreground capitalize">{value}</p>
    </div>
  );
}
