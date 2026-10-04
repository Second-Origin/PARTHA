import { describe, expect, it } from 'vitest';
import { LARGE_GRAPH_EDGE_THRESHOLD, getLayoutedElements, selectVisibleEdges } from './layout';
import type { ArchEdge, ArchLayer, ArchNode } from '@/shared/types/architecture';

function node(id: string, layer: string, relationshipState: ArchNode['relationshipState'] = 'connected'): ArchNode {
  return {
    id,
    name: id,
    type: 'service',
    description: `${id} description`,
    responsibilities: [],
    files: [`${id}.ts`],
    dependencies: [],
    dependents: [],
    estimatedComplexity: 'low',
    estimatedLines: 20,
    tags: [layer],
    layer,
    relationshipState,
  };
}

function edge(source: string, target: string): ArchEdge {
  return {
    id: `${source}->${target}`,
    source,
    target,
    type: 'dependency',
    predicate: 'depends_on',
    truthClass: 'resolved',
    evidence: [],
  };
}

const layers: ArchLayer[] = [
  { id: 'presentation', name: 'Presentation', order: 0, nodes: ['web'] },
  { id: 'business-logic', name: 'Business Logic', order: 1, nodes: ['api', 'worker'] },
  { id: 'infrastructure', name: 'Infrastructure', order: 2, nodes: ['db'] },
];

describe('getLayoutedElements', () => {
  it('places disconnected nodes into readable left-to-right layer columns', () => {
    const result = getLayoutedElements(
      [node('web', 'presentation'), node('api', 'business-logic'), node('worker', 'business-logic'), node('db', 'infrastructure')],
      [edge('web', 'api')],
      { layers },
    );

    const byId = new Map(result.nodes.map((item) => [item.id, item]));
    expect(byId.get('web')!.position.x).toBeLessThan(byId.get('api')!.position.x);
    expect(byId.get('api')!.position.x).toBeLessThan(byId.get('db')!.position.x);
    expect(byId.get('api')!.position.x).toBe(byId.get('worker')!.position.x);
    expect(byId.get('api')!.position.y).not.toBe(byId.get('worker')!.position.y);
  });

  it('keeps node geometry non-overlapping and preserves only real edges', () => {
    const result = getLayoutedElements(
      [node('web', 'presentation'), node('api', 'business-logic'), node('db', 'infrastructure')],
      [edge('web', 'api')],
      { layers },
    );

    const positions = result.nodes.map((item) => item.position);
    for (let left = 0; left < positions.length; left += 1) {
      for (let right = left + 1; right < positions.length; right += 1) {
        const sameColumn = positions[left].x === positions[right].x;
        const sameRow = positions[left].y === positions[right].y;
        expect(sameColumn && sameRow).toBe(false);
      }
    }
    expect(result.edges.map((item) => item.id)).toEqual(['web->api']);
  });

  it('removes collapsed layers and their incident edges', () => {
    const result = getLayoutedElements(
      [node('web', 'presentation'), node('api', 'business-logic'), node('db', 'infrastructure')],
      [edge('web', 'api'), edge('api', 'db')],
      { layers, collapsedLayers: new Set(['business-logic']) },
    );

    expect(result.nodes.map((item) => item.id)).toEqual(['web', 'db']);
    expect(result.edges).toEqual([]);
  });

  it('wraps a busy single semantic layer into a compact deterministic grid', () => {
    const busyNodes = Array.from({ length: 14 }, (_, index) =>
      node(`segment-${String(index + 1).padStart(2, '0')}`, 'shared'),
    );
    const busyLayer: ArchLayer[] = [
      { id: 'shared', name: 'Shared', order: 0, nodes: busyNodes.map((item) => item.id) },
    ];

    const first = getLayoutedElements(busyNodes, [], { layers: busyLayer });
    const second = getLayoutedElements(busyNodes, [], { layers: busyLayer });
    const xPositions = new Set(first.nodes.map((item) => item.position.x));
    const yPositions = new Set(first.nodes.map((item) => item.position.y));

    expect(first).toEqual(second);
    expect(xPositions.size).toBeGreaterThan(1);
    expect(yPositions.size).toBeGreaterThan(1);
    expect(Math.max(...xPositions) - Math.min(...xPositions)).toBeLessThan(1000);
    expect(Math.max(...yPositions) - Math.min(...yPositions)).toBeLessThan(1000);
  });
});

describe('large-graph edge limiting', () => {
  // Distinct directed pairs so the edge count is exact and ids are unique.
  function denseGraph(nodeCount: number, edgeCount: number) {
    const nodes = Array.from({ length: nodeCount }, (_, i) => node(`n${i}`, 'business-logic'));
    const edges: ArchEdge[] = [];
    for (let s = 0; s < nodeCount && edges.length < edgeCount; s += 1) {
      for (let t = 0; t < nodeCount && edges.length < edgeCount; t += 1) {
        if (s !== t) edges.push(edge(`n${s}`, `n${t}`));
      }
    }
    return { nodes, edges };
  }

  it('keeps every edge at the threshold, so small graphs are unchanged', () => {
    const { nodes, edges } = denseGraph(60, LARGE_GRAPH_EDGE_THRESHOLD);
    const result = getLayoutedElements(nodes, edges);
    expect(result.edgesLimited).toBe(false);
    expect(result.edgeCount).toBe(LARGE_GRAPH_EDGE_THRESHOLD);
    expect(result.edges).toHaveLength(LARGE_GRAPH_EDGE_THRESHOLD);
  });

  it('flags the graph as limited one edge past the threshold and still lays out every node', () => {
    const { nodes, edges } = denseGraph(60, LARGE_GRAPH_EDGE_THRESHOLD + 1);
    const result = getLayoutedElements(nodes, edges);
    expect(result.edgesLimited).toBe(true);
    expect(result.edgeCount).toBe(LARGE_GRAPH_EDGE_THRESHOLD + 1);
    expect(result.nodes).toHaveLength(60);
    expect(new Set(result.nodes.map((n) => `${n.position.x},${n.position.y}`)).size).toBe(60);
  });

  it('counts only edges between visible nodes against the threshold', () => {
    const { nodes, edges } = denseGraph(60, LARGE_GRAPH_EDGE_THRESHOLD + 200);
    const hiddenNodes = new Set(nodes.slice(30).map((n) => n.id));
    const result = getLayoutedElements(nodes, edges, { hiddenNodes });
    expect(result.edgeCount).toBeLessThan(edges.length);
    expect(result.edgesLimited).toBe(result.edgeCount > LARGE_GRAPH_EDGE_THRESHOLD);
  });

  it('selectVisibleEdges shows nothing, then only the focused node, when limited', () => {
    const { nodes, edges } = denseGraph(60, LARGE_GRAPH_EDGE_THRESHOLD + 1);
    const { edges: all } = getLayoutedElements(nodes, edges);
    expect(selectVisibleEdges(all, true, null)).toEqual([]);
    const focused = selectVisibleEdges(all, true, 'n0');
    expect(focused.length).toBeGreaterThan(0);
    expect(focused.length).toBeLessThan(all.length);
    expect(focused.every((e) => e.source === 'n0' || e.target === 'n0')).toBe(true);
  });

  it('selectVisibleEdges returns the same edges untouched when not limited', () => {
    const { edges: all } = getLayoutedElements(
      [node('web', 'presentation'), node('api', 'business-logic')],
      [edge('web', 'api')],
    );
    expect(selectVisibleEdges(all, false, null)).toBe(all);
    expect(selectVisibleEdges(all, false, 'web')).toBe(all);
  });
});
