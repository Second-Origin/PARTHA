import { motion } from 'framer-motion';
import { ChevronUp, ChevronDown, ArrowRight } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useArchitectureStore } from '../store';

export function RelationshipPanel() {
  const { model, selectedNodeId, bottomPanelOpen, setBottomPanelOpen } = useArchitectureStore();

  if (!model) return null;

  const selectedNode = selectedNodeId ? model.nodes.find((n) => n.id === selectedNodeId) : null;
  const edges = selectedNodeId
    ? model.edges.filter((e) => e.source === selectedNodeId || e.target === selectedNodeId)
    : [];
  const diagnostics = selectedNode
    ? model.diagnostics.filter((diagnostic) => (
        diagnostic.nodeIds?.includes(selectedNode.id)
        || (diagnostic.path && selectedNode.files.includes(diagnostic.path))
        || diagnostic.subjectKey === selectedNode.id
        || diagnostic.objectKey === selectedNode.id
      ))
    : [];

  const emptyMessage = selectedNode?.relationshipState === 'no-observed-relationships'
    ? 'No observed relationships in the persisted snapshot'
    : selectedNode?.relationshipState === 'unresolved'
      ? 'Relationships were observed but could not be resolved confidently'
      : 'Relationship extraction is not available for this module';

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
              <div className="py-2">
                <p className="text-xs text-muted-foreground">{emptyMessage}</p>
              </div>
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
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-foreground truncate">{targetNode.name}</p>
                        <p className="text-[10px] text-muted-foreground capitalize">
                          {edge.predicate.replace('_', ' ')} · {edge.truthClass}
                        </p>
                        {edge.evidence[0] && (
                          <p
                            className="text-[10px] text-primary truncate"
                            title={`${edge.evidence[0].factId} in snapshot ${edge.evidence[0].snapshotId}`}
                          >
                            {edge.evidence[0].path}:{edge.evidence[0].startLine}
                            {edge.evidence[0].endLine !== edge.evidence[0].startLine && `-${edge.evidence[0].endLine}`}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {selectedNode && diagnostics.length > 0 && (
              <div className="pt-2 space-y-1">
                {diagnostics.map((diagnostic, index) => (
                  <p key={`${diagnostic.code}-${diagnostic.path ?? 'unknown'}-${diagnostic.startLine ?? 'unknown'}-${index}`} className="text-[10px] text-amber-400">
                    {diagnostic.code}: {diagnostic.message}
                    {diagnostic.path && ` (${diagnostic.path}${diagnostic.startLine ? `:${diagnostic.startLine}` : ''})`}
                  </p>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
