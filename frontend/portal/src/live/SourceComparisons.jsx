export default function SourceComparisons({ reports = [], importing = false }) {
  if (!reports.length) return null;
  return <section aria-label="Source-reported average comparisons"><h3>Reported and calculated averages</h3>
    <p>Reported figures never replace calculated values. Differences are non-blocking and remain unresolved after import. Complete academic history is not established by a mark sheet.</p>
    {reports.map((report, index) => {
      const comparison = report.comparison;
      const discrepancy = ['gpa', 'cgpa'].some((key) => comparison[key].status === 'different' || report.comparison_at_import?.[key]?.status === 'different');
      return <div key={report.id || index} className="live-card">
        <h4>{report.academic_session} · {report.semester}</h4>
        <p>{discrepancy ? 'GPA/CGPA discrepancy — unresolved' : 'Source comparison — review unresolved'}</p>
        <p><strong>{importing ? 'Provisional calculated' : 'System-calculated period'} GPA: {comparison.gpa.calculated ?? 'Not comparable'} · CGPA through this period: {comparison.cgpa.calculated ?? 'Not comparable'}</strong></p>
        <p>{comparison.calculation_basis.replaceAll('_', ' ')} · History completeness not established.</p>
        <details><summary>Discrepancy and source details</summary>
          {['gpa', 'cgpa'].map((key) => <p key={key}>{key.toUpperCase()} — source-reported: {comparison[key].reported ?? 'Not reported'}; calculated minus reported: {comparison[key].difference ?? 'Unavailable'}; {comparison[key].status.replaceAll('_', ' ')}.</p>)}
          <p>Previous reported GPA: {comparison.previous_reported_gpa ?? 'Not reported'} (not compared to the current period).</p>
          <p>Review: {report.review_status || comparison.review_status}. Comparison rule: {comparison.comparison_rule}. This is an interim numerical comparison, not a determination that the source is wrong.</p>
          {report.comparison_at_import && <p>Import comparison retained: GPA {report.comparison_at_import.gpa.status}; CGPA {report.comparison_at_import.cgpa.status}.</p>}
          <p>Source page {report.source?.source_page ?? 'not recorded'}, table {report.source?.source_table ?? 'not recorded'}.</p>
          {report.source_sha256 && <p>Source SHA-256: {report.source_sha256} (supplied provenance; not independently authenticated).</p>}
        </details>
      </div>;
    })}
  </section>;
}
