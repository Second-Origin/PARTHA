import { cn } from '@/shared/utils/cn';
import type { ArchitectureDiagnostic } from '@/shared/types/architecture';
import { useArchitectureStore } from '../store';

const SEVERITY_RANK: Record<ArchitectureDiagnostic['severity'], number> = {
  fatal: 0,
  error: 1,
  warning: 2,
  info: 3,
};

/**
 * Complete non-visual list/table equivalent of the Architecture Graph tab (#239):
 * every node, relationship, and diagnostic in the sealed snapshot, sourced from
 * the same `useArchitectureStore` model the canvas reads, kept in sync via
 * `setSelectedNodeId` (the same selection the canvas and NodeInspector use).
 */
export function ArchitectureListView() {
  const { model, selectedNodeId, setSelectedNodeId } = useArchitectureStore();

  if (!model) return null;

  const layerNameById = new Map(model.detectedLayers.map((layer) => [layer.id, layer.name]));
  const layerOrderById = new Map(model.detectedLayers.map((layer) => [layer.id, layer.order]));
  const nodeNameById = new Map(model.nodes.map((node) => [node.id, node.name]));

  const sortedNodes = [...model.nodes].sort((a, b) => {
    const layerDiff =
      (layerOrderById.get(a.layer) ?? Number.MAX_SAFE_INTEGER) -
      (layerOrderById.get(b.layer) ?? Number.MAX_SAFE_INTEGER);
    return layerDiff !== 0 ? layerDiff : a.name.localeCompare(b.name);
  });

  const sortedEdges = [...model.edges].sort((a, b) => {
    const sourceCmp = (nodeNameById.get(a.source) ?? a.source).localeCompare(nodeNameById.get(b.source) ?? b.source);
    if (sourceCmp !== 0) return sourceCmp;
    return (nodeNameById.get(a.target) ?? a.target).localeCompare(nodeNameById.get(b.target) ?? b.target);
  });

  const sortedDiagnostics = [...model.diagnostics].sort((a, b) => {
    const rankDiff = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity];
    return rankDiff !== 0 ? rankDiff : a.code.localeCompare(b.code);
  });

  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-6">
      <p className="text-xs text-muted-foreground">
        Complete non-visual inventory of the same architecture graph shown in the Architecture Graph tab. Activating
        a module or relationship endpoint below selects it, matching the canvas and inspector selection.
      </p>

      <section aria-labelledby="arch-list-nodes-heading">
        <h2 id="arch-list-nodes-heading" className="text-sm font-medium text-foreground mb-2">
          Modules ({sortedNodes.length})
        </h2>
        {sortedNodes.length === 0 ? (
          <p className="text-xs text-muted-foreground">No modules in this snapshot.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead className="text-muted-foreground bg-muted/30">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Name</th>
                  <th scope="col" className="px-3 py-2 font-medium">Type</th>
                  <th scope="col" className="px-3 py-2 font-medium">Layer</th>
                  <th scope="col" className="px-3 py-2 font-medium">Relationship state</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedNodes.map((node) => (
                  <tr key={node.id} className={cn(node.id === selectedNodeId && 'bg-accent/40')}>
                    <th scope="row" className="px-3 py-2 font-normal">
                      <button
                        type="button"
                        onClick={() => setSelectedNodeId(node.id)}
                        aria-current={node.id === selectedNodeId ? 'true' : undefined}
                        className="text-left font-medium text-foreground hover:text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                      >
                        {node.name}
                      </button>
                    </th>
                    <td className="px-3 py-2 capitalize text-muted-foreground">{node.type.replace(/-/g, ' ')}</td>
                    <td className="px-3 py-2 capitalize text-muted-foreground">
                      {(layerNameById.get(node.layer) ?? node.layer).replace(/-/g, ' ')}
                    </td>
                    <td className="px-3 py-2 capitalize text-muted-foreground">
                      {node.relationshipState.replace(/-/g, ' ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="arch-list-edges-heading">
        <h2 id="arch-list-edges-heading" className="text-sm font-medium text-foreground mb-2">
          Relationships ({sortedEdges.length})
        </h2>
        {sortedEdges.length === 0 ? (
          <p className="text-xs text-muted-foreground">No relationships in this snapshot.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[720px] text-left text-xs">
              <thead className="text-muted-foreground bg-muted/30">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Source</th>
                  <th scope="col" className="px-3 py-2 font-medium">Target</th>
                  <th scope="col" className="px-3 py-2 font-medium">Type</th>
                  <th scope="col" className="px-3 py-2 font-medium">Predicate</th>
                  <th scope="col" className="px-3 py-2 font-medium">Truth state</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedEdges.map((edge) => (
                  <tr key={edge.id}>
                    <td className="px-3 py-2">
                      <NodeRefButton id={edge.source} name={nodeNameById.get(edge.source)} onSelect={setSelectedNodeId} />
                    </td>
                    <td className="px-3 py-2">
                      <NodeRefButton id={edge.target} name={nodeNameById.get(edge.target)} onSelect={setSelectedNodeId} />
                    </td>
                    <td className="px-3 py-2 capitalize text-muted-foreground">{edge.type.replace(/-/g, ' ')}</td>
                    <td className="px-3 py-2 capitalize text-muted-foreground">{edge.predicate.replace(/_/g, ' ')}</td>
                    <td className="px-3 py-2 capitalize text-muted-foreground">{edge.truthClass}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="arch-list-diagnostics-heading">
        <h2 id="arch-list-diagnostics-heading" className="text-sm font-medium text-foreground mb-2">
          Diagnostics ({sortedDiagnostics.length})
        </h2>
        {sortedDiagnostics.length === 0 ? (
          <p className="text-xs text-muted-foreground">No diagnostics were recorded for this snapshot.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[720px] text-left text-xs">
              <thead className="text-muted-foreground bg-muted/30">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Severity</th>
                  <th scope="col" className="px-3 py-2 font-medium">Code</th>
                  <th scope="col" className="px-3 py-2 font-medium">Message</th>
                  <th scope="col" className="px-3 py-2 font-medium">Location</th>
                  <th scope="col" className="px-3 py-2 font-medium">Related modules</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedDiagnostics.map((diagnostic, index) => (
                  <tr
                    key={`${diagnostic.code}-${diagnostic.path ?? 'unknown'}-${diagnostic.startLine ?? 'unknown'}-${index}`}
                  >
                    <td className="px-3 py-2 capitalize text-muted-foreground">{diagnostic.severity}</td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">{diagnostic.code}</td>
                    <td className="px-3 py-2 text-foreground">{diagnostic.message}</td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {diagnostic.path
                        ? `${diagnostic.path}${diagnostic.startLine ? `:${diagnostic.startLine}` : ''}`
                        : 'Not localised'}
                    </td>
                    <td className="px-3 py-2">
                      {diagnostic.nodeIds && diagnostic.nodeIds.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {diagnostic.nodeIds.map((id) => (
                            <NodeRefButton key={id} id={id} name={nodeNameById.get(id)} onSelect={setSelectedNodeId} compact />
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function NodeRefButton({
  id,
  name,
  onSelect,
  compact = false,
}: {
  id: string;
  name: string | undefined;
  onSelect: (id: string) => void;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className={cn(
        'text-left text-foreground hover:text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary',
        compact &&
          'inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-2xs font-medium text-muted-foreground hover:text-primary no-underline',
      )}
    >
      {name ?? id}
    </button>
  );
}
