import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import SourceComparisons from './SourceComparisons';

afterEach(cleanup);
const comparison = {
  gpa: { reported: '3.20', calculated: '4.00', difference: '0.80', status: 'different' },
  cgpa: { reported: null, calculated: null, difference: null, status: 'not_reported' },
  previous_reported_gpa: '2.10', review_status: 'unresolved',
  comparison_rule: 'two_decimal_half_up_zero_tolerance_v1', calculation_basis: 'verified_recorded_results',
};

describe('source-reported average comparisons', () => {
  it('emphasizes the calculated value while exposing source values, unresolved status and provenance', () => {
    render(<SourceComparisons reports={[{ academic_session: '2026/2027', semester: 'harmattan',
      source: { source_page: 2, source_table: 1 }, source_sha256: 'synthetic-hash', comparison }]} />);
    expect(screen.getByText(/System-calculated period/).tagName).toBe('STRONG');
    expect(screen.getByText('GPA/CGPA discrepancy — unresolved')).toBeTruthy();
    expect(screen.getByText(/GPA — source-reported: 3.20/)).toBeTruthy();
    expect(screen.getByText(/Previous reported GPA: 2.10/)).toBeTruthy();
    expect(screen.getByText(/Source page 2, table 1/)).toBeTruthy();
    expect(screen.getByText(/source-reported: Not reported/)).toBeTruthy();
  });
  it('keeps unresolved import evidence when the current comparison later matches', () => {
    render(<SourceComparisons reports={[{ academic_session: '2026/2027', semester: 'harmattan',
      comparison: { ...comparison, gpa: { ...comparison.gpa, status: 'matching' } }, comparison_at_import: comparison }]} />);
    expect(screen.getByText(/Import comparison retained: GPA different/)).toBeTruthy();
    expect(screen.getByText('GPA/CGPA discrepancy — unresolved')).toBeTruthy();
  });
});
