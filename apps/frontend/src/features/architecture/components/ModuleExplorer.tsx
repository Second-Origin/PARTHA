import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Layers, Circle } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useArchitectureStore } from '../store';

export function ModuleExplorer() {
  const {
    model,
    expandedModules,
    toggleModule,
    collapsedLayers,
    toggleLayer,
    selectedNodeId,
    setSelectedNodeId,
    setHighlightedNodeIds,
  } = useArchitectureStore();

  if (!model) return null;

  const handleModuleHover = (nodeIds: string[]) => {
    setHighlightedNodeIds(new Set(nodeIds));
  };

  const handleModuleLeave = () => {
    setHighlightedNodeIds(new Set());
  };

  return (
    <div className="w-56 border-r border-border bg-card flex flex-col h-full overflow-hidden">
      <div className="px-3 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Layers className="h-3.5 w-3.5 text-muted-foreground" />
          <h3 className="text-xs font-medium text-foreground">Modules</h3>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-0.5">
        {model.detectedLayers.map((layer) => {
          const isExpanded = expandedModules.has(layer.id);
          const layerNodes = model.nodes.filter((n) => layer.nodes.includes(n.id));

          return (
            <div key={layer.id}>
              <button
                onClick={() => {
                  toggleModule(layer.id);
                  toggleLayer(layer.id);
                }}
                onMouseEnter={() => handleModuleHover(layer.nodes)}
                onMouseLeave={handleModuleLeave}
                aria-expanded={isExpanded}
                aria-pressed={!collapsedLayers.has(layer.id)}
                className={cn(
                  'w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-left hover:bg-accent/50 transition-colors',
                  collapsedLayers.has(layer.id) && 'opacity-70'
                )}
              >
                <ChevronRight
                  className={cn(
                    'h-3 w-3 text-muted-foreground shrink-0 transition-transform duration-150',
                    isExpanded && 'rotate-90'
                  )}
                />
                <span className="text-xs font-medium text-foreground truncate">{layer.name}</span>
                <span className="text-2xs text-muted-foreground ml-auto">{layer.nodes.length}</span>
              </button>

              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="overflow-hidden"
                  >
                    <div className="pl-4 space-y-0.5 py-0.5">
                      {layerNodes.map((node) => (
                        <button
                          key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          onMouseEnter={() => setHighlightedNodeIds(new Set([node.id]))}
                          onMouseLeave={handleModuleLeave}
                          className={cn(
                            'w-full flex items-center gap-2 px-2 py-1 rounded-md text-left transition-colors',
                            selectedNodeId === node.id
                              ? 'bg-primary/10 text-primary'
                              : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                          )}
                        >
                          <Circle className="h-2 w-2 shrink-0 fill-current" />
                          <span className="text-2xs truncate">{node.name}</span>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
