import { Graph, layout } from '@dagrejs/dagre';
import type { Edge } from '@xyflow/react';
import type { ArchNode, ArchEdge, HeatmapMode } from '@/types/architecture';
import type { ArchFlowNode } from './components/ArchitectureNode';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 80;

export function getLayoutedElements(
  archNodes: ArchNode[],
  archEdges: ArchEdge[],
  options?: {
    direction?: 'TB' | 'LR';
    heatmapMode?: HeatmapMode;
    bookmarks?: Set<string>;
    hiddenNodes?: Set<string>;
    isolatedSubtree?: string | null;
  }
): { nodes: ArchFlowNode[]; edges: Edge[] } {
  const direction = options?.direction || 'TB';
  const heatmapMode = options?.heatmapMode || 'none';
  const bookmarks = options?.bookmarks || new Set();
  const hiddenNodes = options?.hiddenNodes || new Set();
  const isolatedSubtree = options?.isolatedSubtree || null;

  let filteredNodes = archNodes.filter((n) => !hiddenNodes.has(n.id));
  let filteredEdges = archEdges;

  if (isolatedSubtree) {
    const subtreeIds = getSubtreeIds(isolatedSubtree, archNodes, archEdges);
    filteredNodes = filteredNodes.filter((n) => subtreeIds.has(n.id));
    filteredEdges = archEdges.filter((e) => subtreeIds.has(e.source) && subtreeIds.has(e.target));
  }

  const g = new Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, ranksep: 80, nodesep: 40, marginx: 40, marginy: 40 });

  filteredNodes.forEach((node) => {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  filteredEdges.forEach((edge) => {
    if (filteredNodes.some((n) => n.id === edge.source) && filteredNodes.some((n) => n.id === edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  });

  layout(g);

  const nodes: ArchFlowNode[] = filteredNodes.map((node) => {
    const pos = g.node(node.id);
    return {
      id: node.id,
      type: 'architectureNode' as const,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        label: node.name,
        nodeType: node.type,
        description: node.description,
        filesCount: node.files.length,
        complexity: node.estimatedComplexity,
        isSelected: false,
        isHighlighted: false,
        heatmapIntensity: computeHeatmapIntensity(node, archNodes, heatmapMode),
        isBookmarked: bookmarks.has(node.id),
      },
    };
  });

  const edges: Edge[] = filteredEdges
    .filter((e) => filteredNodes.some((n) => n.id === e.source) && filteredNodes.some((n) => n.id === e.target))
    .map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: edge.type === 'data-flow' || edge.type === 'event',
      style: {
        stroke: getEdgeColor(edge.type),
        strokeWidth: 1.5,
        opacity: 0.6,
      },
    }));

  return { nodes, edges };
}

function getSubtreeIds(rootId: string, nodes: ArchNode[], edges: ArchEdge[]): Set<string> {
  const ids = new Set<string>([rootId]);
  const queue = [rootId];

  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const edge of edges) {
      if (edge.source === current && !ids.has(edge.target)) {
        ids.add(edge.target);
        queue.push(edge.target);
      }
    }
  }

  const rootNode = nodes.find((n) => n.id === rootId);
  if (rootNode) {
    for (const dep of rootNode.dependents) {
      ids.add(dep);
    }
  }

  return ids;
}

function computeHeatmapIntensity(node: ArchNode, allNodes: ArchNode[], mode: HeatmapMode): number {
  if (mode === 'none') return 0;

  switch (mode) {
    case 'complexity': {
      const map = { low: 0.2, medium: 0.5, high: 0.9 };
      return map[node.estimatedComplexity] || 0;
    }
    case 'usage': {
      const maxDeps = Math.max(...allNodes.map((n) => n.dependents.length), 1);
      return node.dependents.length / maxDeps;
    }
    case 'size': {
      const maxLines = Math.max(...allNodes.map((n) => n.estimatedLines), 1);
      return node.estimatedLines / maxLines;
    }
    case 'critical': {
      const score = (node.dependents.length * 0.4) +
        (node.estimatedComplexity === 'high' ? 0.4 : node.estimatedComplexity === 'medium' ? 0.2 : 0) +
        (node.files.length > 3 ? 0.2 : 0);
      return Math.min(score, 1);
    }
    default:
      return 0;
  }
}

function getEdgeColor(type: string): string {
  switch (type) {
    case 'api-call': return 'hsl(200, 70%, 60%)';
    case 'data-flow': return 'hsl(150, 60%, 50%)';
    case 'event': return 'hsl(280, 60%, 60%)';
    case 'import': return 'hsl(220, 40%, 55%)';
    default: return 'hsl(var(--muted-foreground))';
  }
}
