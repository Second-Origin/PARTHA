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

  it('exposes the full node detail as an accessible name when the card truncates', () => {
    const props = {
      id: 'module:notifications',
      type: 'architectureNode',
      data: {
        label: 'Notifications Delivery Coordinator Service',
        nodeType: 'service',
        layer: 'business-logic',
        relationshipState: 'connected',
        description: 'Fans out delivery attempts across every configured channel.',
        filesCount: 12,
        complexity: 'high',
      },
    } as NodeProps<ArchFlowNode>;

    render(
      <ReactFlowProvider>
        <ArchitectureNode {...props} />
      </ReactFlowProvider>,
    );

    // Card text is truncated to keep node size stable, so the untruncated
    // detail has to remain reachable to assistive tech and on hover (#112).
    const node = screen.getByRole('group', { name: /Notifications Delivery Coordinator Service/ });
    expect(node).toHaveAttribute('title', expect.stringContaining('Fans out delivery attempts'));
    expect(node.getAttribute('aria-label')).toContain('12 files');
    expect(node.getAttribute('aria-label')).toContain('high complexity');
  });

  it('never renders a complexity badge or claim when complexity is not computed (#217)', () => {
    const props = {
      id: 'module:billing',
      type: 'architectureNode',
      data: {
        label: 'Billing',
        nodeType: 'service',
        layer: 'business-logic',
        relationshipState: 'connected',
        description: 'Handles billing.',
        filesCount: 4,
        complexity: 'not_computed',
      },
    } as NodeProps<ArchFlowNode>;

    render(
      <ReactFlowProvider>
        <ArchitectureNode {...props} />
      </ReactFlowProvider>,
    );

    expect(screen.queryByText('not_computed')).not.toBeInTheDocument();
    const node = screen.getByRole('group', { name: /Billing/ });
    expect(node.getAttribute('aria-label')).not.toContain('complexity');
  });
});
