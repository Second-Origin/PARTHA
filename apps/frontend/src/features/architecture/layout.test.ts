import { describe, expect, it } from 'vitest';
import { getLayoutedElements } from './layout';
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
