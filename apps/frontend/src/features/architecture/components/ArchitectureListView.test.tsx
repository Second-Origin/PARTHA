import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { ArchitectureModel, ArchNode } from '@/shared/types/architecture';
import { useArchitectureStore } from '../store';
import { ArchitectureListView } from './ArchitectureListView';

function node(id: string, name: string, layer: string, relationshipState: ArchNode['relationshipState']): ArchNode {
  return {
    id,
    name,
    type: 'service',
    description: '',
    responsibilities: [],
    files: [`src/${name.toLowerCase()}.ts`],
    dependencies: [],
    dependents: [],
    estimatedComplexity: 'low',
    estimatedLines: 1,
    tags: [],
    layer,
    relationshipState,
  };
}

function model(): ArchitectureModel {
  return {
    repositoryId: 'repo-1',
    repositoryName: 'fixture',
    architectureType: 'Repository Architecture',
    detectedLayers: [
      { id: 'presentation', name: 'Presentation', nodes: ['module:beta'], order: 0 },
      { id: 'business-logic', name: 'Business Logic', nodes: ['module:alpha'], order: 1 },
    ],
    nodes: [
      node('module:alpha', 'Alpha', 'business-logic', 'connected'),
      node('module:beta', 'Beta', 'presentation', 'unresolved'),
    ],
    edges: [
      {
        id: 'edge:1',
        source: 'module:alpha',
        target: 'module:beta',
        type: 'import',
        predicate: 'imports',
        truthClass: 'inferred',
        evidence: [{ snapshotId: 'snap_1', factId: 'edge:sha256:abc', path: 'src/alpha.ts', startLine: 4, endLine: 4 }],
      },
    ],
    modules: [],
    requestFlow: [],
    relationshipSnapshotId: 'snap_1',
    diagnostics: [
      {
        code: 'RI-RES-UNRESOLVED',
        category: 'resolution',
        severity: 'warning',
        message: 'Could not resolve a relationship target',
        path: 'src/beta.ts',
        startLine: 9,
        nodeIds: ['module:beta'],
      },
    ],
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

describe('ArchitectureListView', () => {
  beforeEach(() => {
    useArchitectureStore.setState({ model: model(), selectedNodeId: null });
  });

  afterEach(() => {
    useArchitectureStore.setState({ model: null, selectedNodeId: null });
  });

  it('lists every module ordered by layer then name, with type/layer/relationship state', () => {
    render(<ArchitectureListView />);

    const rows = screen.getAllByRole('row').slice(1, 3); // skip header row of the modules table
    expect(rows[0]).toHaveTextContent('Beta');
    expect(rows[0]).toHaveTextContent('Presentation');
    expect(rows[0]).toHaveTextContent('unresolved');
    expect(rows[1]).toHaveTextContent('Alpha');
    expect(rows[1]).toHaveTextContent('Business Logic');
    expect(rows[1]).toHaveTextContent('connected');
  });

  it('selecting a module row updates the shared selection used by the canvas and inspector', () => {
    render(<ArchitectureListView />);

    screen.getAllByRole('button', { name: 'Alpha' })[0].click();

    expect(useArchitectureStore.getState().selectedNodeId).toBe('module:alpha');
  });

  it('shows relationship source/target names, predicate, and truth state, and syncs selection', () => {
    render(<ArchitectureListView />);

    expect(screen.getByText('imports')).toBeInTheDocument();
    expect(screen.getByText('inferred')).toBeInTheDocument();

    screen.getAllByRole('button', { name: 'Beta' })[0].click();
    expect(useArchitectureStore.getState().selectedNodeId).toBe('module:beta');
  });

  it('shows diagnostics with severity, message, location, and a link back to the related module', () => {
    render(<ArchitectureListView />);

    expect(screen.getByText('Could not resolve a relationship target')).toBeInTheDocument();
    expect(screen.getByText('src/beta.ts:9')).toBeInTheDocument();

    const relatedModuleButtons = screen.getAllByRole('button', { name: 'Beta' });
    relatedModuleButtons[relatedModuleButtons.length - 1].click();
    expect(useArchitectureStore.getState().selectedNodeId).toBe('module:beta');
  });

  it('renders explicit empty states when a snapshot has no relationships or diagnostics', () => {
    useArchitectureStore.setState({
      model: { ...model(), edges: [], diagnostics: [] },
    });

    render(<ArchitectureListView />);

    expect(screen.getByText('No relationships in this snapshot.')).toBeInTheDocument();
    expect(screen.getByText('No diagnostics were recorded for this snapshot.')).toBeInTheDocument();
  });
});
