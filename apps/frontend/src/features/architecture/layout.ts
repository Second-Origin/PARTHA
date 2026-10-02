import { Graph, layout } from '@dagrejs/dagre';
import type { Edge } from '@xyflow/react';
import type { ArchLayer, ArchNode, ArchEdge, HeatmapMode } from '@/shared/types/architecture';
import type { ArchFlowNode } from './components/ArchitectureNode';

export const ARCH_NODE_WIDTH = 220;
export const ARCH_NODE_HEIGHT = 112;
// Keep the review-default graph inside a laptop viewport at the readable
// 0.85x zoom floor. Wider graphs remain pannable, but common five-layer and
// busy single-layer fixtures should not open with partially clipped cards.
const RANK_GAP = 50;
const NODE_GAP = 35;

/**
 * Relationship count above which the graph stops drawing every edge at once.
 *
 * A real 343-module repository carries ~13.8k relationships (mostly
 * module-to-package dependency edges). Feeding them all to Dagre and React Flow
 * froze the tab for ~160s. Dagre's cost grows steeply with edge count (343
 * nodes: 500 edges ~0.4s, 1,000 ~6s, 1,500 ~29s), so the threshold sits where
 * layout stays around a second. Above it the canvas shows only the selected
 * module's relationships; the full set stays available through the
 * Relationship panel and the List View. Graphs at or below it are unchanged.
 */
export const LARGE_GRAPH_EDGE_THRESHOLD = 500;

/** Edges to put on the canvas: all of them, or only the focused node's in large-graph mode. */
export function selectVisibleEdges(edges: Edge[], limited: boolean, focusNodeId: string | null): Edge[] {
  if (!limited) return edges;
  if (!focusNodeId) return [];
  return edges.filter((edge) => edge.source === focusNodeId || edge.target === focusNodeId);
}

export function getLayoutedElements(
  archNodes: ArchNode[],
  archEdges: ArchEdge[],
  options?: {
    direction?: 'TB' | 'LR';
    heatmapMode?: HeatmapMode;
    bookmarks?: Set<string>;
    hiddenNodes?: Set<string>;
    isolatedSubtree?: string | null;
    layers?: ArchLayer[];
    collapsedLayers?: Set<string>;
  }
): { nodes: ArchFlowNode[]; edges: Edge[]; edgesLimited: boolean; edgeCount: number } {
  const direction = options?.direction || 'LR';
  const heatmapMode = options?.heatmapMode || 'none';
  const bookmarks = options?.bookmarks || new Set();
  const hiddenNodes = options?.hiddenNodes || new Set();
  const isolatedSubtree = options?.isolatedSubtree || null;
  const collapsedLayers = options?.collapsedLayers || new Set();

  let filteredNodes = archNodes.filter(
    (node) => !hiddenNodes.has(node.id) && !collapsedLayers.has(node.layer)
  );
  let filteredEdges = archEdges;

  if (isolatedSubtree) {
    const subtreeIds = getSubtreeIds(isolatedSubtree, archNodes, archEdges);
    filteredNodes = filteredNodes.filter((n) => subtreeIds.has(n.id));
    filteredEdges = archEdges.filter((e) => subtreeIds.has(e.source) && subtreeIds.has(e.target));
  }

  const g = new Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, ranksep: RANK_GAP, nodesep: NODE_GAP, marginx: 40, marginy: 40 });

  filteredNodes.forEach((node) => {
    g.setNode(node.id, { width: ARCH_NODE_WIDTH, height: ARCH_NODE_HEIGHT });
  });

  const filteredNodeIds = new Set(filteredNodes.map((node) => node.id));
  const visibleEdges = filteredEdges.filter(
    (edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target),
  );
  const edgesLimited = visibleEdges.length > LARGE_GRAPH_EDGE_THRESHOLD;
  // Node positions come from the layer grid below; Dagre only orders nodes
  // within a layer. In large-graph mode skip its edge work entirely.
  if (!edgesLimited) {
    visibleEdges.forEach((edge) => g.setEdge(edge.source, edge.target));
  }

  layout(g);

  const orderedLayers = getOrderedLayers(filteredNodes, options?.layers);
  const layerPositions = getLayerPositions(filteredNodes, orderedLayers, g, direction);

  const nodes: ArchFlowNode[] = filteredNodes.map((node) => {
    const pos = layerPositions.get(node.id) || g.node(node.id);
    return {
      id: node.id,
      type: 'architectureNode' as const,
      initialWidth: ARCH_NODE_WIDTH,
      initialHeight: ARCH_NODE_HEIGHT,
      position: { x: pos.x - ARCH_NODE_WIDTH / 2, y: pos.y - ARCH_NODE_HEIGHT / 2 },
      data: {
        label: node.name,
        nodeType: node.type,
        layer: node.layer,
        relationshipState: node.relationshipState,
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

  const edges: Edge[] = visibleEdges
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

  return { nodes, edges, edgesLimited, edgeCount: visibleEdges.length };
}

function getOrderedLayers(nodes: ArchNode[], layers?: ArchLayer[]): ArchLayer[] {
  const visibleNodeIds = new Set(nodes.map((node) => node.id));
  const knownLayers = new Map((layers || []).map((layer) => [layer.id, layer]));
  const layerIds = new Set(nodes.map((node) => node.layer));

  return [...layerIds]
    .sort((left, right) => {
      const leftOrder = knownLayers.get(left)?.order ?? Number.MAX_SAFE_INTEGER;
      const rightOrder = knownLayers.get(right)?.order ?? Number.MAX_SAFE_INTEGER;
      return leftOrder - rightOrder || left.localeCompare(right);
    })
    .map((id) => ({
      id,
      name: knownLayers.get(id)?.name || id.replace('-', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
      order: knownLayers.get(id)?.order ?? Number.MAX_SAFE_INTEGER,
      nodes: (knownLayers.get(id)?.nodes || nodes.filter((node) => node.layer === id).map((node) => node.id))
        .filter((nodeId) => visibleNodeIds.has(nodeId)),
    }));
}

function getLayerPositions(
  nodes: ArchNode[],
  layers: ArchLayer[],
  graph: Graph,
  direction: 'TB' | 'LR',
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  let layerCursor = 0;

  layers.forEach((layer, layerIndex) => {
    const layerNodes = layer.nodes
      .map((nodeId) => nodesById.get(nodeId))
      .filter((node): node is ArchNode => node !== undefined)
      .sort((left, right) => {
        const leftY = graph.node(left.id)?.y ?? 0;
        const rightY = graph.node(right.id)?.y ?? 0;
        return leftY - rightY || left.name.localeCompare(right.name) || left.id.localeCompare(right.id);
      });

    if (direction === 'LR') {
      // A semantic layer is a band, not necessarily one physical column.
      // Deterministically wrap a busy layer into sub-columns so a 14-node
      // single-layer repository opens as a compact grid instead of one very
      // tall column with an empty canvas beside it (#112).
      // A small semantic layer reads best as one column. Only wrap layers
      // large enough to become taller than the review canvas.
      const maxRows = layerNodes.length <= 4
        ? Math.max(1, layerNodes.length)
        : Math.max(2, Math.ceil(Math.sqrt(layerNodes.length)));
      const columnCount = Math.max(1, Math.ceil(layerNodes.length / maxRows));
      layerNodes.forEach((node, nodeIndex) => {
        const columnIndex = Math.floor(nodeIndex / maxRows);
        const rowIndex = nodeIndex % maxRows;
        const rowsInColumn = Math.min(maxRows, layerNodes.length - columnIndex * maxRows);
        const offset = -((rowsInColumn - 1) * (ARCH_NODE_HEIGHT + NODE_GAP)) / 2;
        positions.set(node.id, {
          x: layerCursor + columnIndex * (ARCH_NODE_WIDTH + NODE_GAP) + ARCH_NODE_WIDTH / 2,
          y: offset + rowIndex * (ARCH_NODE_HEIGHT + NODE_GAP) + ARCH_NODE_HEIGHT / 2,
        });
      });
      layerCursor +=
        columnCount * ARCH_NODE_WIDTH
        + Math.max(0, columnCount - 1) * NODE_GAP
        + RANK_GAP;
    } else {
      const offset = -((layerNodes.length - 1) * (ARCH_NODE_WIDTH + NODE_GAP)) / 2;
      layerNodes.forEach((node, nodeIndex) => {
        positions.set(node.id, {
          x: offset + nodeIndex * (ARCH_NODE_WIDTH + NODE_GAP) + ARCH_NODE_WIDTH / 2,
          y: layerIndex * (ARCH_NODE_HEIGHT + RANK_GAP) + ARCH_NODE_HEIGHT / 2,
        });
      });
    }
  });

  return positions;
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
    case 'usage': {
      const maxDeps = Math.max(...allNodes.map((n) => n.dependents.length), 1);
      return node.dependents.length / maxDeps;
    }
    case 'critical': {
      // Real signals only (#217): dependents count and file count, both from
      // the sealed snapshot. No complexity term -- nothing measures it today.
      const maxDeps = Math.max(...allNodes.map((n) => n.dependents.length), 1);
      const score = (node.dependents.length / maxDeps) * 0.6 + (node.files.length > 3 ? 0.4 : 0);
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
