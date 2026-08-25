import { describe, expect, it } from 'vitest';
import svg from './landing-reference.svg?raw';

/** The light canvas turned out to have the exact same baked-in switcher
 * mockup as the dark one -- same pill, same three icon paths, just at its
 * own y-offset (this file isn't composited by any build script; it's the
 * original, whole asset). Never checked for it while only the dark canvas
 * was in scope, so it stayed live-in-production for two whole fix rounds.
 * See landing-reference-dark.test.ts for why a component test can't catch
 * this class of bug. */
describe('landing-reference.svg', () => {
  it('does not contain the baked-in switcher pill from the raw Figma export', () => {
    expect(svg).not.toContain('rx="18.5" stroke="#FA4D01"');
  });

  it('removed exactly the switcher icon paths, not unrelated footer content', () => {
    for (const prefix of ['M1538.89 5548', 'M1504 5537.2', 'M1460.53 5542.97']) {
      expect(svg).not.toContain(`d="${prefix}`);
    }
  });

  it('still has the rest of the artwork intact -- a substantial path count remains', () => {
    const pathCount = (svg.match(/<path/g) ?? []).length;
    expect(pathCount).toBeGreaterThan(300);
  });
});
