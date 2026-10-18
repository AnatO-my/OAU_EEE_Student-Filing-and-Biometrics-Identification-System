import { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getAttendanceSession, getCurrentAcademicSession, importPendingCaptures, listAttendanceRecords, listAttendanceSessions, previewPendingCaptures } from '../api';
import { useAuth } from '../auth/useAuth';
import { hasPermission, workspaceHome } from '../auth/permissions';
import { LoadState, Pager } from '../components/LiveData';
import { useRemote } from '../useRemote';

function time(value) {
  return value ? new Date(value).toLocaleString() : 'Not recorded';
}

function CurrentSession() {
  const resource = useRemote(getCurrentAcademicSession);
  return <LoadState resource={resource}>{data => <p>Current academic session: {data.name || 'Not selected'}</p>}</LoadState>;
}

export function PendingCaptureUpload({ sessionId }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [uncertain, setUncertain] = useState(false);
  async function inspect(event) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setPreview(null); setReviewed(false); setReceipt(null); setUncertain(false);
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('Choose a capture file no larger than 2 MiB.');
      const body = await file.arrayBuffer();
      const data = await previewPendingCaptures(sessionId, body);
      if (!/^[a-f0-9]{64}$/.test(data.file_sha256 || '')) throw new Error('The server did not return a valid file preview.');
      setPreview({ body, data });
    } catch (failure) { setError(failure.message || 'Unable to preview this file.'); }
    finally { setBusy(false); }
  }
  async function commit() {
    if (!preview || !reviewed || busy || receipt) return;
    setBusy(true); setError(''); setUncertain(false);
    try { setReceipt(await importPendingCaptures(sessionId, preview.body, preview.data.file_sha256)); }
    catch (failure) { setError(failure.message || 'Unable to import this file.'); setUncertain(!failure.status || failure.status < 400 || failure.status >= 500); }
    finally { setBusy(false); }
  }
  return <section className="live-card"><h2>Import pending captures</h2><p>Preview the original capture file for this class, review its counts, then confirm the import. Captures remain pending identity and timing review and do not mark students present or absent.</p>
    <form onSubmit={inspect}><label>Capture file<input type="file" accept=".jsonl,.ndjson,application/x-ndjson" disabled={busy || uncertain} onChange={event => { setFile(event.target.files?.[0] || null); setPreview(null); setReviewed(false); setReceipt(null); setError(''); setUncertain(false); }} /></label><button disabled={!file || busy || uncertain}>{busy ? 'Working…' : 'Preview captures'}</button></form>
    {error && <p role="alert">{error}</p>}
    {uncertain && <p role="status">The import outcome is not confirmed. Retry the same import to recover its receipt before choosing another file.</p>}
    {preview && <div><p>Batch: {preview.data.batch_id}</p><p>File events: {preview.data.event_count} · New events: {preview.data.new_events} · Existing events: {preview.data.existing_events}</p>
      {preview.data.recovery_review_required && <p>Interrupted capture recovery needs review.</p>}
      {!receipt && <><label><span><input type="checkbox" checked={reviewed} disabled={busy} onChange={event => setReviewed(event.target.checked)} /> I have reviewed this file and class.</span></label><button onClick={commit} disabled={busy || !reviewed}>{uncertain ? 'Retry same import' : 'Confirm import'}</button></>}
    </div>}
    {receipt && <div role="status"><p>Import receipt: {receipt.receipt_id}</p><p>{receipt.new_events} new captures; {receipt.existing_events} already stored. {receipt.replayed ? 'Original receipt recovered.' : 'File received.'}</p><p>Pending review. Keep the original device file.</p></div>}
  </section>;
}

function ClassRecords({ sessionId, user }) {
  const [page, setPage] = useState(1);
  const detailLoad = useCallback(signal => getAttendanceSession(sessionId, signal), [sessionId]);
  const detail = useRemote(detailLoad);
  const load = useCallback(signal => listAttendanceRecords(sessionId, page, signal), [sessionId, page]);
  const records = useRemote(load);
  return <section className="live-card"><h2>Class attendance records</h2>
    <LoadState resource={detail}>{data => <p>{data.title} · {data.status} · {time(data.starts_at)}</p>}</LoadState>
    <LoadState resource={records}>{data => <>{data.results.length ? <div className="live-table"><table><thead><tr><th>Student ID</th><th>Status</th><th>Recorded at</th><th>Reason</th></tr></thead><tbody>{data.results.map(row => <tr key={row.id}><td>{row.student_id}</td><td>{row.status}</td><td>{time(row.recorded_at)}</td><td>{row.reason}</td></tr>)}</tbody></table></div> : <p>No attendance records have been recorded for this class.</p>}<Pager data={data} page={page} onChange={setPage} /></>}</LoadState>
    {!detail.loading && !detail.error && hasPermission(user, 'attendance.import_pending_captures') && <PendingCaptureUpload sessionId={sessionId} />}
  </section>;
}

export default function AttendanceDashboard() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = useCallback(signal => listAttendanceSessions(page, signal), [page]);
  const sessions = useRemote(load);
  async function logout() {
    if (busy) return;
    setBusy(true); setError('');
    try { await signOut(); navigate('/login', { replace: true }); }
    catch (failure) { setError(failure.message || 'Unable to sign out.'); }
    finally { setBusy(false); }
  }
  return <main className="live-portal"><header className="live-heading"><div><p>EEE OAU · Student class attendance</p><h1>Class attendance</h1></div><button disabled={busy} onClick={logout}>{busy ? 'Signing out…' : 'Log out'}</button></header>
    <Link to={workspaceHome(user)}>Return to workspace</Link>{error && <p role="alert">{error}</p>}
    {user.role === 'hod' && <CurrentSession />}
    <section className="live-card"><h2>Visible classes</h2><p>Select a class to view its student records. Course assignments and permissions are checked by the server.</p>
      <LoadState resource={sessions}>{data => <>{data.results.length ? <><p>{data.results.filter(row => row.status === 'open').length} open classes on this page.</p><label>Class<select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Choose a class</option>{data.results.map(row => <option key={row.id} value={row.id}>{row.title} · {row.status} · {time(row.starts_at)}</option>)}</select></label></> : <p>No attendance classes are visible to your account.</p>}<Pager data={data} page={page} onChange={value => { setPage(value); setSelected(''); }} /></>}</LoadState>
    </section>
    {selected && !sessions.loading && !sessions.error && <ClassRecords key={`${user.id}-${selected}`} sessionId={selected} user={user} />}
  </main>;
}
