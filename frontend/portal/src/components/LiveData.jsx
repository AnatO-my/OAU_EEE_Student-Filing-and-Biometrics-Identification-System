export function LoadState({ resource, children }) {
  if (resource.loading) return <p role="status">Loading records…</p>;
  if (resource.error) return <div><p role="alert">{resource.error.status === 404 ? 'This record or feature is unavailable on the connected server.' : resource.error.message || 'Unable to load records.'}</p><button onClick={resource.retry}>Try again</button></div>;
  return children(resource.data);
}

export function Pager({ data, page, onChange }) {
  return <div className="live-actions"><button disabled={page === 1} onClick={() => onChange(page - 1)}>Previous page</button><span>Page {page} · {data.count} records</span><button disabled={!data.next} onClick={() => onChange(page + 1)}>Next page</button></div>;
}

export function ProfileFields({ student }) {
  const fields = [['Name', student.full_name], ['Student identifier', student.identifier_value], ['Level', student.current_level], ['Admission year', student.admission_year], ['Phone', student.phone_number], ['Academic status', student.academic_status]];
  return <dl className="live-fields">{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 'Not recorded'}</dd></div>)}</dl>;
}
