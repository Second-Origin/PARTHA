import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReactFlowProvider, type NodeProps } from '@xyflow/react';
import type { ArchFlowNode } from './ArchitectureNode';
import { ArchitectureNode } from './ArchitectureNode';

describe('ArchitectureNode', () => {
  it('keeps the name, type, layer, and relationship state visible', () => {
    const props = {
      id: 'module:orders',
      type: 'architectureNode',
      data: {
        label: 'Orders',
        nodeType: 'service',
        layer: 'business-logic',
        relationshipState: 'connected',
        description: 'Coordinates order processing.',
        filesCount: 3,
        complexity: 'medium',
      },
    } as NodeProps<ArchFlowNode>;

    render(
      <ReactFlowProvider>
        <ArchitectureNode {...props} />
      </ReactFlowProvider>,
    );

    expect(screen.getByText('Orders')).toBeInTheDocument();
    expect(screen.getByText('Service · Business Logic')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });
});
