import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { ArchitectureModel, ArchNode } from '@/shared/types/architecture';
import { useArchitectureStore } from '../store';
import { RelationshipPanel } from './RelationshipPanel';

function node(id: string, name: string, relationshipState: ArchNode['relationshipState']): ArchNode {
  return {
    id,
    name,
    type: 'shared-library',
    description: '',
    responsibilities: [],
    files: [`src/${name.toLowerCase()}.ts`],
    dependencies: [],
    dependents: [],
    estimatedComplexity: 'low',
    estimatedLines: 1,
    tags: [],
    layer: 'shared',
    relationshipState,
  };
}

function model(): ArchitectureModel {
  return {
    repositoryId: 'repo-1',
    repositoryName: 'fixture',
    architectureType: 'Repository Architecture',
    detectedLayers: [],
    nodes: [node('module:alpha', 'Alpha', 'connected'), node('module:beta', 'Beta', 'connected')],
    edges: [
      {
        id: 'edge:1',
        source: 'module:alpha',
        target: 'module:beta',
        type: 'import',
        predicate: 'imports',
        truthClass: 'inferred',
        evidence: [
          {
            snapshotId: 'snap_1',
            factId: 'edge:sha256:abc',
            path: 'src/alpha.ts',
            startLine: 4,
            endLine: 4,
          },
        ],
      },
    ],
    modules: [],
    requestFlow: [],
    relationshipSnapshotId: 'snap_1',
    diagnostics: [],
    summary: {
      language: 'TypeScript',
      framework: 'Unknown',
      totalModules: 2,
      totalNodes: 2,
      entryPoint: '/',
      architecturePattern: 'Repository Architecture',
    },
  };
}

describe('RelationshipPanel', () => {
  beforeEach(() => {
    useArchitectureStore.setState({
      model: model(),
      selectedNodeId: 'module:alpha',
      bottomPanelOpen: true,
    });
  });

  it('shows edge truth class and its persisted evidence span', () => {
    render(<RelationshipPanel />);

    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('imports · inferred')).toBeInTheDocument();
    expect(screen.getByText('src/alpha.ts:4')).toHaveAttribute(
      'title',
      'edge:sha256:abc in snapshot snap_1',
    );
  });

  it('distinguishes no observed relationship from missing extraction', () => {
    const isolated = node('module:isolated', 'Isolated', 'no-observed-relationships');
    useArchitectureStore.setState({
      model: { ...model(), nodes: [isolated], edges: [] },
      selectedNodeId: isolated.id,
    });
    const { rerender } = render(<RelationshipPanel />);
    expect(screen.getByText('No observed relationships in the persisted snapshot')).toBeInTheDocument();

    useArchitectureStore.setState({
      model: { ...model(), nodes: [{ ...isolated, relationshipState: 'not-extracted' }], edges: [] },
    });
    rerender(<RelationshipPanel />);
    expect(screen.getByText('Relationship extraction is not available for this module')).toBeInTheDocument();
  });
});
