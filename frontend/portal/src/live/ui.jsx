export function Alert({ children }) {
  return children ? <p className="live-alert" role="alert">{children}</p> : null;
}

export function Empty({ children }) { return <p className="live-empty"><span className="live-empty-mark" aria-hidden="true"><PortalIcon name="records" /></span><span>{children}</span></p>; }

export function Pager({ page, data, onChange, disabled }) {
  return <div className="live-pager"><span>{data?.count ?? 0} records · Page {page}</span>
    <button disabled={disabled || page === 1} onClick={() => onChange(page - 1)}>Previous</button>
    <button disabled={disabled || !data?.next} onClick={() => onChange(page + 1)}>Next</button></div>;
}

export function RemoteState({ resource, children }) {
  if (resource.loading) return <p role="status" className="live-empty"><span className="live-loading-mark" aria-hidden="true" />Loading records…</p>;
  if (resource.error) return <><Alert>{resource.error}</Alert><button onClick={resource.reload}>Retry loading</button></>;
  return children(resource.data);
}

export function Table({ headings, children }) {
  return <div className="live-table" role="region" aria-label={`${headings.join(', ')} table. Scroll horizontally if needed.`} tabIndex={0}><table><thead><tr>{headings.map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}

export function PortalIcon({ name, className = '' }) {
  const drawings = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>,
    students: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M17 15a5 5 0 0 1 4 5v1" /></>,
    profile: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
    results: <><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M8 8h8M8 12h3M8 16h6M15 12h1" /></>,
    courses: <><path d="M3 4h7a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H3V4Zm18 0h-5a3 3 0 0 0-3 3v14a4 4 0 0 1 4-2h4V4Z" /></>,
    imports: <><path d="M8 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6H8Z" /><path d="M14 3v6h6M12 17v-5m-3 3 3-3 3 3" /></>,
    attendance: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4M17 3v4M3 11h18m-13 5 3 3 5-5" /></>,
    'guardian-results': <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6" /></>,
    'academic-session': <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4M17 3v4M3 11h18M7 15h3M14 15h3" /></>,
    account: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" /><circle cx="15" cy="17" r="3" /></>,
    messages: <><path d="M21 15a3 3 0 0 1-3 3H9l-6 4V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v9Z" /><path d="M7 8h10M7 12h7" /></>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    logout: <><path d="M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5M10 12h11m-4-4 4 4-4 4" /></>,
    records: <><path d="M5 3h10l4 4v14H5V3Z" /><path d="M14 3v5h5M9 12h6M9 16h4" /></>,
    brand: <><path d="m3 7 9-4 9 4-9 4-9-4Zm3 3v7l6 4 6-4v-7M12 11v10" /></>,
  };
  return <svg className={`live-icon ${className}`} width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{drawings[name] || drawings.records}</svg>;
}
