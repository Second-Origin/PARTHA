import { describe, expect, it } from 'vitest';
import { buildSearchResultDestination } from './searchNavigation';

describe('buildSearchResultDestination', () => {
  it('deep-links file results to the Explorer with the selected path', () => {
    expect(
      buildSearchResultDestination('repo-1', {
        type: 'file',
        path: '/docs/Architecture & Design.md',
      }),
    ).toBe('/repositories/repo-1?tab=Explorer&path=%2Fdocs%2FArchitecture+%26+Design.md');
  });

  it('keeps repository-only results on the repository landing route', () => {
    expect(
      buildSearchResultDestination('repo-1', { type: 'repository', path: '' }),
    ).toBe('/repositories/repo-1');
  });
});
