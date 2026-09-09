import axe from 'axe-core';

/**
 * Accessibility smoke check for a rendered surface.
 *
 * This is deliberately a smoke check, not a WCAG 2.2 AA audit (#118 tracks
 * that). It runs axe-core in jsdom, which can evaluate structure, naming, roles
 * and relationships but cannot evaluate anything that needs real layout or
 * painting — colour contrast and visual focus order in particular. Rules that
 * jsdom cannot judge honestly are disabled rather than allowed to report a
 * meaningless pass.
 */
const JSDOM_UNSUPPORTED_RULES = [
  // Needs computed colour and a rendered box.
  'color-contrast',
  // Needs real layout to know what actually overlaps or scrolls.
  'scrollable-region-focusable',
];

export interface AxeViolationSummary {
  id: string;
  impact: string | null;
  help: string;
  nodes: string[];
}

export async function findAccessibilityViolations(
  container: HTMLElement,
): Promise<AxeViolationSummary[]> {
  const results = await axe.run(container, {
    rules: Object.fromEntries(JSDOM_UNSUPPORTED_RULES.map((id) => [id, { enabled: false }])),
    resultTypes: ['violations'],
  });

  return results.violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact ?? null,
    help: violation.help,
    nodes: violation.nodes.map((node) => node.html),
  }));
}

/** Formats violations so a failure names the rule and the offending markup. */
export function describeViolations(violations: AxeViolationSummary[]): string {
  return violations
    .map(
      (violation) =>
        `${violation.id} (${violation.impact ?? 'unknown'}): ${violation.help}\n    ${violation.nodes.join('\n    ')}`,
    )
    .join('\n');
}
