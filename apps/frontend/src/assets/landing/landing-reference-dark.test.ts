import { describe, expect, it } from 'vitest';
import svg from './landing-reference-dark.svg?raw';

/** The dark canvas is a flattened image -- component tests never parse its
 * content, so a duplicate baked into the artwork itself (as opposed to a
 * duplicate React component) can only be caught by inspecting the file
 * directly. This guards against the exact regression that shipped once
 * already: the raw Figma export had a static mockup of the theme switcher
 * drawn into the footer, and it stayed invisible only as long as the real
 * ThemeSwitcher had an opaque background covering it. Once that background
 * was removed to match the reference, the baked-in one became visible on
 * its own, rendering as a second switcher. */
describe('landing-reference-dark.svg', () => {
  it('does not contain the baked-in switcher pill from the raw Figma export', () => {
    expect(svg).not.toContain('rx="18.5" stroke="#FA4D01"');
  });

  it('still contains the rest of the footer artwork the pill was removed from', () => {
    // Text in this export is outlined vector paths, not <text> elements, so
    // there's no literal copy to grep -- assert structurally instead: the
    // footer block is still present and still has substantially more than
    // just the 4 elements (1 pill + 3 icons) that were removed from it.
    const footerIndex = svg.indexOf('id="footer"');
    expect(footerIndex).toBeGreaterThan(-1);
    const footerBlock = svg.slice(footerIndex);
    const pathCount = (footerBlock.match(/<path/g) ?? []).length;
    expect(pathCount).toBeGreaterThan(20);
  });

  it('removed exactly the switcher icon paths, not unrelated footer content', () => {
    // The three icon paths this fix stripped out, identified by the same
    // path-data prefixes used to remove them (laptop, sun, moon).
    for (const prefix of ['M1538.89 423', 'M1504 412.199', 'M1460.53 417.965']) {
      expect(svg).not.toContain(`d="${prefix}`);
    }
  });
});
