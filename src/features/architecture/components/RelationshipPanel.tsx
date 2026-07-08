import { motion } from 'framer-motion';
import { ChevronUp, ChevronDown, ArrowRight } from 'lucide-react';
import { cn } from '@/utils/cn';
import { useArchitectureStore } from '../store';

export function RelationshipPanel() {
  const { model, selectedNodeId, bottomPanelOpen, setBottomPanelOpen } = useArchitectureStore();

  if (!model) return null;

  const selectedNode = selectedNodeId ? model.nodes.find((n) => n.id === selectedNodeId) : null;
  const edges = selectedNodeId
    ? model.edges.filter((e) => e.source === selectedNodeId || e.target === selectedNodeId)
    : [];

  return (
    <div className="border-t border-border bg-card">
      <button
        onClick={() => setBottomPanelOpen(!bottomPanelOpen)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-accent/30 transition-colors"
      >
        <span className="text-xs font-medium text-foreground">
          Relationships {selectedNode ? `- ${selectedNode.name}` : ''}{' '}
          {edges.length > 0 && <span className="text-muted-foreground">({edges.length})</span>}
        </span>
        {bottomPanelOpen ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>

      {bottomPanelOpen && (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: 'auto' }}
          className="overflow-hidden max-h-40 overflow-y-auto scrollbar-thin"
        >
          <div className="px-4 pb-3">
            {!selectedNode ? (
              <p className="text-xs text-muted-foreground py-2">Select a node to view its relationships</p>
            ) : edges.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">No relationships found</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 pt-1">
                {edges.map((edge) => {
                  const isOutgoing = edge.source === selectedNodeId;
                  const targetId = isOutgoing ? edge.target : edge.source;
                  const targetNode = model.nodes.find((n) => n.id === targetId);
                  if (!targetNode) return null;

                  return (
                    <div
                      key={edge.id}
                      className="flex items-center gap-2 rounded-md border border-border px-3 py-2"
                    >
                      <span className={cn(
                        'text-[10px] font-medium px-1.5 py-0.5 rounded',
                        isOutgoing ? 'bg-blue-500/10 text-blue-400' : 'bg-emerald-500/10 text-emerald-400'
                      )}>
                        {isOutgoing ? 'OUT' : 'IN'}
                      </span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{targetNode.name}</p>
                        <p className="text-[10px] text-muted-foreground capitalize">{edge.type.replace('-', ' ')}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
