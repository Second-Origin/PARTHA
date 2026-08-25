import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeSwitcher } from './ThemeSwitcher';

describe('ThemeSwitcher', () => {
  it('renders System, Light, and Dark as a radiogroup', () => {
    render(<ThemeSwitcher preference="system" onChange={vi.fn()} />);

    const group = screen.getByRole('radiogroup', { name: 'Theme' });
    const options = screen.getAllByRole('radio');
    expect(options.map((option) => option.getAttribute('aria-label'))).toEqual(['System', 'Light', 'Dark']);
    expect(group).toBeInTheDocument();
  });

  it('marks only the current preference as checked', () => {
    render(<ThemeSwitcher preference="dark" onChange={vi.fn()} />);

    expect(screen.getByRole('radio', { name: 'System' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('radio', { name: 'Light' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('radio', { name: 'Dark' })).toHaveAttribute('aria-checked', 'true');
  });

  it('calls onChange with the clicked option', () => {
    const onChange = vi.fn();
    render(<ThemeSwitcher preference="light" onChange={onChange} />);

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }));

    expect(onChange).toHaveBeenCalledWith('dark');
  });

  it('renders every option identically regardless of selection -- the reference art has no active-state indicator', () => {
    render(<ThemeSwitcher preference="dark" onChange={vi.fn()} />);

    const options = screen.getAllByRole('radio');
    const classSets = options.map((option) => option.className);
    expect(new Set(classSets).size).toBe(1);
    expect(classSets[0]).not.toMatch(/bg-primary|text-primary-foreground/);
  });
});
