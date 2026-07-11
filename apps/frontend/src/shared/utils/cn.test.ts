import { describe, expect, it } from 'vitest';
import { cn, formatFileSize } from './cn';

describe('cn', () => {
  it('joins conditional classes and drops falsy values', () => {
    const hidden = [].length > 0;
    expect(cn('base', hidden && 'hidden', 'extra')).toBe('base extra');
  });

  it('resolves tailwind conflicts in favour of the last class', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
    expect(cn('text-sm', 'text-lg')).toBe('text-lg');
  });
});

describe('formatFileSize', () => {
  it('formats zero', () => {
    expect(formatFileSize(0)).toBe('0 B');
  });

  it('formats whole units', () => {
    expect(formatFileSize(1024)).toBe('1 KB');
    expect(formatFileSize(1024 * 1024)).toBe('1 MB');
  });

  it('rounds to one decimal', () => {
    expect(formatFileSize(1536)).toBe('1.5 KB');
  });
});
