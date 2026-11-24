import { describe, expect, it } from 'vitest';

import {
  formatIndicatorValue,
  formatScore,
} from '../src/utils/format.js';

describe('formatIndicatorValue', () => {
  it('shows N/A rather than zero for a missing value', () => {
    expect(formatIndicatorValue(null, 'ratio')).toBe('N/A');
    expect(formatIndicatorValue(undefined, 'percent')).toBe('N/A');
  });

  it('formats percentages with a sign', () => {
    expect(formatIndicatorValue(12.345, 'percent')).toBe('12.3%');
  });

  it('formats days without decimals', () => {
    expect(formatIndicatorValue(32.85, 'days')).toBe('33 days');
  });

  it('formats coverage in times', () => {
    expect(formatIndicatorValue(9, 'times')).toBe('9.00×');
  });

  it('formats a plain ratio to two decimals', () => {
    expect(formatIndicatorValue(2.5, 'ratio')).toBe('2.50');
  });
});

describe('formatScore', () => {
  it('shows N/A for a missing score', () => {
    expect(formatScore(null)).toBe('N/A');
  });

  it('shows one decimal place', () => {
    expect(formatScore(72.456)).toBe('72.5');
  });
});

describe('exact amounts', () => {
  it('adds typed amounts in whole cents without floating-point drift', async () => {
    const { toCents, formatAmount } = await import('../src/utils/format.js');
    expect(toCents('60000') + toCents('49999.99')).toBe(toCents('109999.99'));
    expect(toCents('0.1') + toCents('0.2')).toBe(toCents('0.3'));
    expect(formatAmount(109999.99)).toBe('109,999.99');
  });
});
