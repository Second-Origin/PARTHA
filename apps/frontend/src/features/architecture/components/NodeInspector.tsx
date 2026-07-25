import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  ChevronDown,
  FileCode,
  GitBranch,
  Tag,
  Layers,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { ArchNode } from '@/shared/types/architecture';
import { useArchitectureStore } from '../store';

interface NodeInspectorProps {
  node: ArchNode;
  onClose: () => void;
}

export function NodeInspector({ node, onClose }: NodeInspectorProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const dialog = closeRef.current?.closest<HTMLElement>('[role="dialog"]');
      const focusable = Array.from(
        dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])') ?? [],
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={`Architecture node: ${node.name}`}
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 20, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="flex h-full w-80 flex-col overflow-hidden border-l border-border bg-card max-md:fixed max-md:inset-y-0 max-md:right-0 max-md:z-50 max-md:w-full"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-foreground truncate">{node.name}</h3>
          <p className="text-2xs text-muted-foreground capitalize">{node.type.replace('-', ' ')}</p>
        </div>
        <button
          ref={closeRef}
          type="button"
          aria-label="Close architecture node inspector"
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors shrink-0"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-3">
        <InspectorSection title="Overview" defaultOpen>
          <p className="text-xs text-muted-foreground leading-relaxed">{node.description}</p>
          <div className="grid grid-cols-2 gap-2 mt-3">
            <MiniStat label="Complexity" value={node.estimatedComplexity} />
            <MiniStat label="Est. Lines" value={String(node.estimatedLines)} />
            <MiniStat label="Layer" value={node.layer.replace('-', ' ')} />
            <MiniStat label="Files" value={String(node.files.length)} />
          </div>
        </InspectorSection>

        <InspectorSection title="Responsibilities" icon={Layers} defaultOpen>
          <ul className="space-y-1">
            {node.responsibilities.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                <span className="text-primary mt-1 shrink-0">-</span>
                {r}
              </li>
            ))}
          </ul>
        </InspectorSection>

        <InspectorSection title="Files" icon={FileCode}>
          {node.files.length === 0 ? (
            <p className="text-xs text-muted-foreground">No files mapped</p>
          ) : (
            <ul className="space-y-1">
              {node.files.map((f) => (
                <li key={f} className="text-xs text-muted-foreground font-mono truncate">
                  {f}
                </li>
              ))}
            </ul>
          )}
        </InspectorSection>

        <InspectorSection title="Dependencies" icon={GitBranch}>
          {node.dependencies.length === 0 ? (
            <p className="text-xs text-muted-foreground">No dependencies</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {node.dependencies.map((d) => (
                <DepBadge key={d} id={d} direction="out" />
              ))}
            </div>
          )}
        </InspectorSection>

        <InspectorSection title="Dependents" icon={GitBranch}>
          {node.dependents.length === 0 ? (
            <p className="text-xs text-muted-foreground">No dependents</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {node.dependents.map((d) => (
                <DepBadge key={d} id={d} direction="in" />
              ))}
            </div>
          )}
        </InspectorSection>

        <InspectorSection title="Tags" icon={Tag}>
          <div className="flex flex-wrap gap-1.5">
            {node.tags.map((t) => (
              <span
                key={t}
                className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-2xs text-muted-foreground"
              >
                {t}
              </span>
            ))}
          </div>
        </InspectorSection>

      </div>
    </motion.div>
  );
}

function InspectorSection({
  title,
  icon: Icon,
  defaultOpen = false,
  children,
}: {
  title: string;
  icon?: typeof FileCode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-accent/30 transition-colors"
      >
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
        <span className="text-xs font-medium text-foreground flex-1">{title}</span>
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 text-muted-foreground transition-transform duration-150',
            open && 'rotate-180'
          )}
        />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted/50 px-2.5 py-1.5">
      <p className="text-2xs text-muted-foreground">{label}</p>
      <p className="text-xs font-medium text-foreground capitalize">{value}</p>
    </div>
  );
}

function DepBadge({ id, direction }: { id: string; direction: 'in' | 'out' }) {
  const { setSelectedNodeId, model } = useArchitectureStore();
  const node = model?.nodes.find((n) => n.id === id);
  const label = node?.name || id;

  return (
    <button
      onClick={() => setSelectedNodeId(id)}
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-2xs font-medium transition-colors',
        direction === 'out'
          ? 'bg-primary/10 text-primary hover:bg-primary/20'
          : 'bg-accent text-accent-foreground hover:bg-accent/80'
      )}
    >
      {label}
    </button>
  );
}
