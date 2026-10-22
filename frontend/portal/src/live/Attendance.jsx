import { useRef, useState } from 'react';
import * as api from '../api';
import { Alert, Empty, Pager, RemoteState, Table } from './ui';
import { formatDate, hasPermission, isHod, useRemote } from './resources';

function StudentAttendance() {
  const [page, setPage] = useState(1);
  const resource = useRemote((signal) => api.getMyAttendance(page, signal), [page]);
  return <section className="live-card"><h2>My attendance history</h2><p>These are your recorded marks. A roster member without a record is not automatically absent.</p>
    <RemoteState resource={resource}>{(data) => <>{!data.results.length ? <Empty>No attendance has been recorded.</Empty> : <Table headings={['Class session', 'Offering ID', 'Status', 'Recorded']}>
      {data.results.map((row) => <tr key={row.id}><td>{row.session_id}</td><td>{row.session__offering_id}</td><td>{row.status}</td><td>{formatDate(row.recorded_at)}</td></tr>)}</Table>}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState></section>;
}

export function PendingUpload({ sessionId, onImported = () => {} }) {
  const [file, setFile] = useState(null), [preview, setPreview] = useState(null), [receipt, setReceipt] = useState(null);
  const [reviewed, setReviewed] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function inspect() {
    if (!file || busy) return;
    setBusy(true); setError(''); setReceipt(null); setPreview(null); setReviewed(false);
    try { setPreview(await api.previewPendingCaptures(sessionId, file)); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function commit() {
    if (!file || !preview || !reviewed || busy) return;
    setBusy(true); setError('');
    try { setReceipt(await api.importPendingCaptures(sessionId, file, preview.file_sha256)); onImported(); }
    catch (err) { setError(`${err.message} Keep the selected file. Retrying these same bytes recovers the original receipt if the import already succeeded.`); }
    finally { setBusy(false); }
  }
  function select(event) {
    const value = event.target.files?.[0];
    setPreview(null); setReceipt(null); setReviewed(false); setError('');
    if (value?.size > 2 * 1024 * 1024) { setFile(null); setError('The capture file must be no larger than 2 MiB.'); return; }
    setFile(value || null);
  }
  return <section className="live-inset"><h3>Pending capture evidence</h3><p>Upload the original JSONL file. Import preserves unidentified evidence for later review; it does not mark attendance.</p>
    <Alert>{error}</Alert><label>Capture JSONL file (maximum 2 MiB)<input type="file" accept=".jsonl,.ndjson,application/x-ndjson" onChange={select} disabled={busy} /></label>
    <button disabled={!file || busy} onClick={inspect}>{busy ? 'Processing file…' : 'Preview capture file'}</button>
    {preview && <div className="live-inset"><h4>Preview — {preview.event_count} captures</h4><dl className="live-details"><div><dt>New events</dt><dd>{preview.new_events}</dd></div><div><dt>Existing events</dt><dd>{preview.existing_events}</dd></div>
      <div><dt>Batch ID</dt><dd>{preview.batch_id}</dd></div><div><dt>Whole-file SHA-256</dt><dd>{preview.file_sha256}</dd></div><div><dt>Recovery review</dt><dd>{preview.recovery_review_required ? 'Required' : 'Not flagged'}</dd></div></dl>
      <p>Identity and timing review are required. The device is not authenticated. Retain the device file after import.</p>
      <label className="live-check"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} disabled={busy || !!receipt} /> I reviewed this preview and the pending review flags.</label>
      <button className="live-primary" disabled={!reviewed || busy || !!receipt} onClick={commit}>{busy ? 'Importing…' : 'Import reviewed capture file'}</button>
    </div>}
    {receipt && <div className="live-notice" role="status"><strong>{receipt.replayed ? 'Original receipt recovered' : 'Import receipt saved'}</strong><p>Receipt: {receipt.receipt_id}</p><p>{receipt.new_events} new events · {receipt.existing_events} existing · {formatDate(receipt.received_at)}</p><p>Pending identity and timing review. No attendance marks were created. Keep the original file.</p></div>}
  </section>;
}

function ManualRecord({ session, onSaved }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const attempt = useRef(null);
  async function submit(event) {
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget));
    const signature = JSON.stringify({ session: session.id, ...values });
    if (attempt.current?.signature !== signature) attempt.current = { signature, eventId: crypto.randomUUID() };
    setBusy(true); setError(''); setNotice('');
    try {
      const data = await api.recordManualAttendance(session.id, { ...values, event_id: attempt.current.eventId });
      setNotice(data.replayed ? 'The original event was recovered.' : data.duplicate ? 'This student already has a record. No mark was overwritten.' : 'Manual attendance recorded.');
      onSaved();
    } catch (err) { setError(`${err.message} An unchanged retry uses the same event ID.`); }
    finally { setBusy(false); }
  }
  return <details><summary>Record manual attendance</summary><p>This records authorized manual attendance with server time. It is not fingerprint proof.</p><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}
    <form className="live-form" onSubmit={submit}><label>Student on the fixed class roster<select name="student" required disabled={busy}><option value="">Choose a student record ID</option>{session.student_ids.map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
      <label>Reason<textarea name="reason" maxLength="1000" required disabled={busy} /></label><button className="live-primary" disabled={busy || !session.student_ids.length}>Record present</button></form></details>;
}

function Correction({ row, onSaved }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    try { await api.correctAttendanceRecord(row.id, data.get('status'), data.get('reason')); onSaved(); }
    catch (err) { setError(`${err.message} Refresh records before retrying an uncertain correction.`); }
    finally { setBusy(false); }
  }
  return <details><summary>Correct record {row.id}</summary><Alert>{error}</Alert><form onSubmit={submit} className="live-form"><label>Corrected status<select name="status" defaultValue={row.status} disabled={busy}><option value="present">Present</option><option value="absent">Absent</option></select></label>
    <label>Correction reason<textarea name="reason" required maxLength="1000" disabled={busy} /></label><button disabled={busy}>Save audited correction</button></form></details>;
}

function PendingHistory({ sessionId, revision }) {
  const [page, setPage] = useState(1);
  const resource = useRemote((signal) => api.listPendingCaptureBatches(sessionId, page, signal), [sessionId, page, revision]);
  return <details><summary>Imported pending batches</summary><RemoteState resource={resource}>{(data) => <>{!data.results.length ? <Empty>No pending batches have been imported.</Empty> : <Table headings={['Batch ID', 'Events', 'Received', 'Review']}>
    {data.results.map((row) => <tr key={row.batch_id}><td>{row.batch_id}</td><td>{row.event_count}</td><td>{formatDate(row.received_at)}</td><td>Identity and timing required{row.recovery_review_required ? ' · Recovery review required' : ''}</td></tr>)}</Table>}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState></details>;
}

function SessionDetail({ sessionId, user, onClosed }) {
  const [page, setPage] = useState(1), [error, setError] = useState(''), [busy, setBusy] = useState(false), [imports, setImports] = useState(0);
  const detail = useRemote((signal) => api.getAttendanceSession(sessionId, signal), [sessionId]);
  const records = useRemote((signal) => api.listAttendanceRecords(sessionId, page, signal), [sessionId, page]);
  async function close(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { await api.closeAttendanceSession(sessionId); detail.reload(); onClosed(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="live-card"><h2>Selected class</h2><Alert>{error}</Alert><RemoteState resource={detail}>{(session) => <>
    <h3>{session.title}</h3><p>Offering {session.offering} · {session.status} · Roster revision {session.roster_revision}</p><p>{formatDate(session.starts_at)} – {formatDate(session.ends_at)}</p>
    {session.status === 'open' && hasPermission(user, 'attendance.manage_attendance') && <form className="live-filters" onSubmit={close}><label className="live-check"><input type="checkbox" required disabled={busy} /> Close this class permanently</label><button disabled={busy}>Close class</button></form>}
    {hasPermission(user, 'attendance.record_attendance') && <ManualRecord session={session} onSaved={records.reload} />}
  </>}</RemoteState><h3>Attendance records</h3><p className="live-hint">Student identifiers below are backend record IDs. Unrecorded roster members are not inferred absent.</p>
    <RemoteState resource={records}>{(data) => <>{!data.results.length ? <Empty>No attendance has been recorded for this class.</Empty> : <Table headings={['Student record ID', 'Status', 'Recorded', 'Reason', ...(hasPermission(user, 'attendance.correct_attendance') ? ['Correction'] : [])]}>
      {data.results.map((row) => <tr key={row.id}><td>{row.student_id}</td><td>{row.status}</td><td>{formatDate(row.recorded_at)}</td><td>{row.reason}</td>{hasPermission(user, 'attendance.correct_attendance') && <td><Correction row={row} onSaved={records.reload} /></td>}</tr>)}</Table>}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState>
    {hasPermission(user, 'attendance.import_pending_captures') && <><PendingUpload sessionId={sessionId} onImported={() => setImports((value) => value + 1)} /><PendingHistory sessionId={sessionId} revision={imports} /></>}
  </section>;
}

function OpenClass({ onSaved }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); const form = event.currentTarget, data = Object.fromEntries(new FormData(form)); setBusy(true); setError('');
    try {
      const row = await api.openAttendanceSession({ offering: Number(data.offering), title: data.title, starts_at: new Date(data.starts_at).toISOString(), ends_at: new Date(data.ends_at).toISOString() });
      form.reset(); onSaved(row.id);
    } catch (err) { setError(`${err.message} Check the class list before retrying an uncertain request.`); } finally { setBusy(false); }
  }
  return <details><summary>Open a class</summary><p>The offering must be current, assigned to you where required, and have an HOD-approved roster.</p><Alert>{error}</Alert>
    <form className="live-form" onSubmit={submit}><label>Course offering ID<input name="offering" type="number" min="1" required disabled={busy} /></label><label>Class title<input name="title" maxLength="200" required disabled={busy} /></label>
      <label>Starts at (this computer’s local time)<input name="starts_at" type="datetime-local" required disabled={busy} /></label><label>Ends at (this computer’s local time)<input name="ends_at" type="datetime-local" required disabled={busy} /></label>
      <button disabled={busy} className="live-primary">{busy ? 'Opening…' : 'Open class'}</button></form></details>;
}

function Roster({ offeringId }) {
  const resource = useRemote(async (signal) => {
    const first = await api.getAttendanceRoster(offeringId, 1, signal), rows = [...first.results];
    let next = first.next;
    for (let page = 2; next; page += 1) {
      if (page > 500) throw new Error('Too many roster candidates. Contact the administrator.');
      const data = await api.getAttendanceRoster(offeringId, page, signal); rows.push(...data.results); next = data.next;
    }
    return { ...first, results: rows };
  }, [offeringId]);
  return <RemoteState resource={resource}>{(data) => <RosterForm key={`${offeringId}:${data.confirmed_revision}`} data={data} offeringId={offeringId} onSaved={resource.reload} />}</RemoteState>;
}

function RosterForm({ data, offeringId, onSaved }) {
  const [selected, setSelected] = useState(() => new Set(data.confirmed_student_ids)), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const candidates = new Map(data.results.map((row) => [row.student_id, row]));
  data.confirmed_student_ids.forEach((id) => { if (!candidates.has(id)) candidates.set(id, { student_id: id, full_name: 'Previously confirmed member — review eligibility', reasons: [] }); });
  function toggle(id) { setSelected((old) => { const next = new Set(old); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }
  async function submit(event) {
    event.preventDefault(); const extra = new FormData(event.currentTarget).get('extra').split(/[\s,]+/).filter(Boolean), ids = [...new Set([...selected, ...extra])];
    setBusy(true); setError('');
    try { await api.confirmAttendanceRoster(offeringId, ids, data.confirmed_revision); onSaved(); }
    catch (err) { setError(`${err.message} Reload the roster to review its current revision before another confirmation.`); } finally { setBusy(false); }
  }
  return <form className="live-form live-wide" onSubmit={submit}><h3>Confirm course roster</h3><p>Current revision: {data.confirmed_revision}. Suggestions are not proof of current registration. Review exemptions and retakers before confirming.</p><Alert>{error}</Alert>
    {[...candidates.values()].map((row) => <label key={row.student_id} className="live-check"><input type="checkbox" checked={selected.has(row.student_id)} onChange={() => toggle(row.student_id)} disabled={busy} /><span>{row.full_name} · {row.identifier_value || row.student_id}<small className="live-hint"> {row.reasons.join(', ').replaceAll('_', ' ')}</small></span></label>)}
    {!candidates.size && <Empty>No students were suggested. Add eligible record IDs after checking their registrations.</Empty>}
    <label>Additional active undergraduate student record IDs (one per line)<textarea name="extra" disabled={busy} /></label><p>{selected.size} existing/candidate students selected. At most 1000 unique members are accepted.</p>
    <label className="live-check"><input type="checkbox" required disabled={busy} /> I reviewed the complete membership for this offering.</label><button className="live-primary" disabled={busy}>Confirm roster at revision {data.confirmed_revision}</button><button type="button" disabled={busy} onClick={onSaved}>Reload roster</button>
  </form>;
}

function CoursePreparation() {
  const resource = useRemote(async (signal) => {
    const [offerings, courses, sessions] = await Promise.all([api.collectPages(api.listCourseOfferings, signal), api.collectPages(api.listCourses, signal), api.collectPages(api.listAcademicSessions, signal)]);
    return offerings.map((row) => ({ ...row, label: `${courses.find((item) => item.id === row.course)?.code || row.course} · ${sessions.find((item) => item.id === row.academic_session)?.name || row.academic_session} · ${row.semester} · ${row.level} level · ID ${row.id}` }));
  }, []);
  const [offering, setOffering] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  async function assign(event) {
    event.preventDefault(); const values = new FormData(event.currentTarget); setBusy(true); setError(''); setNotice('');
    try { await api.setAttendanceStaff(offering, Number(values.get('staff')), values.get('active') === 'on'); setNotice('Course staff assignment updated.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <details className="live-card"><summary>HOD · Course rosters and staff assignment</summary><RemoteState resource={resource}>{(rows) => <>
    <label>Course offering<select value={offering} onChange={(event) => setOffering(event.target.value)}><option value="">Choose a course offering</option>{rows.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
    {!rows.length && <Empty>Configure the course offering in academic administration first.</Empty>}
    {offering && <><Roster key={offering} offeringId={offering} /><details><summary>Set a course staff assignment</summary><p>Use the staff account’s numeric ID from administration. Assignment and attendance permissions are separate.</p><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}
      <form className="live-form" onSubmit={assign}><label>Staff account ID<input name="staff" type="number" min="1" required disabled={busy} /></label><label className="live-check"><input name="active" type="checkbox" defaultChecked disabled={busy} /> Assignment active</label><button disabled={busy}>Save assignment</button></form></details></>}
  </>}</RemoteState></details>;
}

export default function Attendance({ user }) {
  const [selected, setSelected] = useState('');
  const resource = useRemote((signal) => user.role === 'student' ? Promise.resolve([]) : api.collectPages(api.listAttendanceSessions, signal), [user.role]);
  if (user.role === 'student') return <StudentAttendance />;
  return <>{isHod(user) && <CoursePreparation />}<section className="live-card"><div className="live-row"><h2>Classes</h2><button onClick={resource.reload}>Refresh classes</button></div>
    <RemoteState resource={resource}>{(rows) => <><p>{rows.length} accessible classes · {rows.filter((row) => row.status === 'open').length} open</p>
      {!rows.length ? <Empty>No classes are available for your current course assignments.</Empty> : <><label>Choose a class<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">Choose a class</option>{rows.map((row) => <option key={row.id} value={row.id}>{row.title} · Offering {row.offering} · {row.status}</option>)}</select></label>
        <Table headings={['Class', 'Offering ID', 'Starts', 'Status']} >{rows.map((row) => <tr key={row.id}><td><button onClick={() => setSelected(row.id)}>{row.title}</button></td><td>{row.offering}</td><td>{formatDate(row.starts_at)}</td><td>{row.status}</td></tr>)}</Table></>}
    </>}</RemoteState>{hasPermission(user, 'attendance.manage_attendance') && <OpenClass onSaved={(id) => { setSelected(id); resource.reload(); }} />}</section>
    {selected && <SessionDetail key={selected} sessionId={selected} user={user} onClosed={resource.reload} />}
  </>;
}
