import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { toPng, toSvg } from 'html-to-image';
import { AnimatePresence } from 'framer-motion';

import { ArchitectureNode } from './ArchitectureNode';
import { NodeInspector } from './NodeInspector';
import { ModuleExplorer } from './ModuleExplorer';
import { GraphToolbar } from './GraphToolbar';
import { ArchSummaryBar } from './ArchSummaryBar';
import { RequestFlow } from './RequestFlow';
import { NodeContextMenu } from './NodeContextMenu';
import { HeatmapControls } from './HeatmapControls';
import { RelationshipPanel } from './RelationshipPanel';
import { getLayoutedElements } from '../layout';
import { useArchitectureStore } from '../store';
import { cn } from '@/utils/cn';
import type { DataSource } from '@/types';
import type { ArchitectureModel } from '@/types/architecture';

const nodeTypes = { architectureNode: ArchitectureNode };

interface ArchWorkspaceInnerProps {
  model: ArchitectureModel;
  source?: DataSource | null;
}

function ArchWorkspaceInner({ model, source }: ArchWorkspaceInnerProps) {
  const reactFlowInstance = useReactFlow();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const {
    selectedNodeId,
    setSelectedNodeId,
    highlightedNodeIds,
    setHighlightedNodeIds,
    searchQuery,
    showGrid,
    showMiniMap,
    inspectorOpen,
    setInspectorOpen,
    explorerOpen,
    activeTab,
    setActiveTab,
    heatmapMode,
    bookmarkedNodes,
    hiddenNodes,
    showAllNodes,
    isolatedSubtree,
    setIsolatedSubtree,
    openContextMenu,
    closeContextMenu,
  } = useArchitectureStore();

  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => getLayoutedElements(model.nodes, model.edges, {
      heatmapMode,
      bookmarks: bookmarkedNodes,
      hiddenNodes,
      isolatedSubtree,
    }),
    [model, heatmapMode, bookmarkedNodes, hiddenNodes, isolatedSubtree]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = getLayoutedElements(model.nodes, model.edges, {
      heatmapMode,
      bookmarks: bookmarkedNodes,
      hiddenNodes,
      isolatedSubtree,
    });
    setNodes(newNodes);
    setEdges(newEdges);
  }, [heatmapMode, bookmarkedNodes, hiddenNodes, isolatedSubtree, model, setNodes, setEdges]);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isSelected: n.id === selectedNodeId,
          isHighlighted: highlightedNodeIds.has(n.id),
        },
      }))
    );
  }, [selectedNodeId, highlightedNodeIds, setNodes]);

  useEffect(() => {
    if (!searchQuery) {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          style: undefined,
        }))
      );
      return;
    }
    const q = searchQuery.toLowerCase();
    setNodes((nds) =>
      nds.map((n) => {
        const archNode = model.nodes.find((an) => an.id === n.id);
        const matches =
          archNode &&
          (archNode.name.toLowerCase().includes(q) ||
            archNode.type.toLowerCase().includes(q) ||
            archNode.tags.some((t) => t.includes(q)) ||
            archNode.layer.toLowerCase().includes(q));
        return {
          ...n,
          style: matches ? undefined : { opacity: 0.15 },
        };
      })
    );
  }, [searchQuery, setNodes, model.nodes]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      closeContextMenu();
      setSelectedNodeId(node.id);
    },
    [setSelectedNodeId, closeContextMenu]
  );

  const handleNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setIsolatedSubtree(isolatedSubtree === node.id ? null : node.id);
    },
    [setIsolatedSubtree, isolatedSubtree]
  );

  const handleNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault();
      openContextMenu(node.id, { x: event.clientX, y: event.clientY });
    },
    [openContextMenu]
  );

  const handleNodeMouseEnter = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const archNode = model.nodes.find((n) => n.id === node.id);
      if (!archNode) return;
      const neighborIds = new Set([
        node.id,
        ...archNode.dependencies,
        ...archNode.dependents,
      ]);
      setHighlightedNodeIds(neighborIds);
    },
    [model.nodes, setHighlightedNodeIds]
  );

  const handleNodeMouseLeave = useCallback(() => {
    setHighlightedNodeIds(new Set());
  }, [setHighlightedNodeIds]);

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
    setInspectorOpen(false);
    closeContextMenu();
  }, [setSelectedNodeId, setInspectorOpen, closeContextMenu]);

  const handleFitView = useCallback(() => {
    reactFlowInstance.fitView({ padding: 0.2, duration: 300 });
  }, [reactFlowInstance]);

  const handleZoomIn = useCallback(() => {
    reactFlowInstance.zoomIn({ duration: 200 });
  }, [reactFlowInstance]);

  const handleZoomOut = useCallback(() => {
    reactFlowInstance.zoomOut({ duration: 200 });
  }, [reactFlowInstance]);

  const handleResetLayout = useCallback(() => {
    setIsolatedSubtree(null);
    showAllNodes();
    const { nodes: newNodes, edges: newEdges } = getLayoutedElements(model.nodes, model.edges, {
      heatmapMode,
      bookmarks: bookmarkedNodes,
    });
    setNodes(newNodes);
    setEdges(newEdges);
    setTimeout(() => reactFlowInstance.fitView({ padding: 0.2, duration: 300 }), 50);
  }, [model, setNodes, setEdges, reactFlowInstance, heatmapMode, bookmarkedNodes, setIsolatedSubtree, showAllNodes]);

  const handleExportPng = useCallback(() => {
    const el = document.querySelector('.react-flow') as HTMLElement;
    if (!el) return;
    toPng(el, { backgroundColor: '#0a0e1a' }).then((dataUrl) => {
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `${model.repositoryName}-architecture.png`;
      a.click();
    });
  }, [model.repositoryName]);

  const handleExportSvg = useCallback(() => {
    const el = document.querySelector('.react-flow') as HTMLElement;
    if (!el) return;
    toSvg(el, { backgroundColor: '#0a0e1a' }).then((dataUrl) => {
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `${model.repositoryName}-architecture.svg`;
      a.click();
    });
  }, [model.repositoryName]);

  const handleExportJson = useCallback(() => {
    const json = JSON.stringify(model, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${model.repositoryName}-architecture.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [model]);

  const handleExportMarkdown = useCallback(() => {
    const md = generateMarkdown(model);
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${model.repositoryName}-architecture.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [model]);

  const handleToggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const handleFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, []);

  const selectedArchNode = useMemo(
    () => (selectedNodeId ? model.nodes.find((n) => n.id === selectedNodeId) : null),
    [selectedNodeId, model.nodes]
  );

  return (
    <div ref={containerRef} className="flex flex-col h-full bg-background">
      <ArchSummaryBar model={model} source={source} />

      <div className="flex items-center justify-between gap-2 px-4 py-2 border-b border-border">
        <div className="flex items-center gap-1">
          <TabButton active={activeTab === 'graph'} onClick={() => setActiveTab('graph')}>
            Architecture Graph
          </TabButton>
          <TabButton active={activeTab === 'request-flow'} onClick={() => setActiveTab('request-flow')}>
            Request Flow
          </TabButton>
          <TabButton active={activeTab === 'heatmap'} onClick={() => setActiveTab('heatmap')}>
            Heatmap
          </TabButton>
        </div>
        {activeTab === 'heatmap' && <HeatmapControls />}
        {isolatedSubtree && (
          <button
            onClick={() => setIsolatedSubtree(null)}
            className="text-[11px] text-primary hover:text-primary/80 font-medium transition-colors"
          >
            Exit Isolation
          </button>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {explorerOpen && (activeTab === 'graph' || activeTab === 'heatmap') && <ModuleExplorer />}

        <div className="flex-1 relative flex flex-col">
          <div className="flex-1 relative">
            {(activeTab === 'graph' || activeTab === 'heatmap') ? (
              <>
                <GraphToolbar
                  onFitView={handleFitView}
                  onZoomIn={handleZoomIn}
                  onZoomOut={handleZoomOut}
                  onResetLayout={handleResetLayout}
                  onExportPng={handleExportPng}
                  onExportSvg={handleExportSvg}
                  onExportJson={handleExportJson}
                  onExportMarkdown={handleExportMarkdown}
                  onToggleFullscreen={handleToggleFullscreen}
                  isFullscreen={isFullscreen}
                />
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onNodeClick={handleNodeClick}
                  onNodeDoubleClick={handleNodeDoubleClick}
                  onNodeContextMenu={handleNodeContextMenu}
                  onNodeMouseEnter={handleNodeMouseEnter}
                  onNodeMouseLeave={handleNodeMouseLeave}
                  onPaneClick={handlePaneClick}
                  nodeTypes={nodeTypes}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                  minZoom={0.1}
                  maxZoom={3}
                  proOptions={{ hideAttribution: true }}
                >
                  {showGrid && (
                    <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="hsl(var(--border))" />
                  )}
                  {showMiniMap && (
                    <MiniMap
                      nodeColor={() => 'hsl(var(--primary))'}
                      maskColor="hsl(var(--background) / 0.8)"
                      className="!bg-card !border-border !rounded-lg"
                      style={{ width: 140, height: 90 }}
                    />
                  )}
                </ReactFlow>
              </>
            ) : (
              <div className="flex-1 overflow-y-auto scrollbar-thin">
                <RequestFlow steps={model.requestFlow} />
              </div>
            )}
          </div>
          <RelationshipPanel />
        </div>

        <AnimatePresence>
          {inspectorOpen && selectedArchNode && (
            <NodeInspector
              node={selectedArchNode}
              onClose={() => {
                setSelectedNodeId(null);
                setInspectorOpen(false);
              }}
            />
          )}
        </AnimatePresence>
      </div>

      <NodeContextMenu />
    </div>
  );
}

export function ArchWorkspace({ model, source }: { model: ArchitectureModel; source?: DataSource | null }) {
  return (
    <ReactFlowProvider>
      <ArchWorkspaceInner model={model} source={source} />
    </ReactFlowProvider>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
        active ? 'bg-accent text-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
      )}
    >
      {children}
    </button>
  );
}

function generateMarkdown(model: ArchitectureModel): string {
  const lines: string[] = [
    `# ${model.repositoryName} - Architecture`,
    '',
    `**Pattern:** ${model.architectureType}`,
    `**Language:** ${model.summary.language}`,
    `**Framework:** ${model.summary.framework}`,
    `**Entry Point:** ${model.summary.entryPoint}`,
    '',
    '## Layers',
    '',
  ];

  for (const layer of model.detectedLayers) {
    lines.push(`### ${layer.name}`);
    lines.push('');
    const layerNodes = model.nodes.filter((n) => layer.nodes.includes(n.id));
    for (const node of layerNodes) {
      lines.push(`- **${node.name}** (${node.type}) - ${node.description}`);
      if (node.files.length > 0) {
        lines.push(`  - Files: ${node.files.join(', ')}`);
      }
    }
    lines.push('');
  }

  lines.push('## Dependencies');
  lines.push('');
  for (const edge of model.edges) {
    const source = model.nodes.find((n) => n.id === edge.source);
    const target = model.nodes.find((n) => n.id === edge.target);
    if (source && target) {
      lines.push(`- ${source.name} -> ${target.name} (${edge.type})`);
    }
  }

  return lines.join('\n');
}
