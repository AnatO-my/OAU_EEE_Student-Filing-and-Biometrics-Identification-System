import { useRef, useState } from 'react';
import { apiRequest } from '../api';
import { Alert, Empty, RemoteState, Table } from './ui';
import { formatDate, hasPermission, useRemote } from './resources';

const root = '/api/attendance/';
function eventPayload(ref, body) {
  const key = JSON.stringify(body);
  if (ref.current?.key !== key) ref.current = { key, id: crypto.randomUUID() };
  return { ...body, event_id: ref.current.id };
}
function Expand({ title, children }) {
  const [open, setOpen] = useState(false);
  return <details className="live-card" onToggle={event => setOpen(event.currentTarget.open)}><summary>{title}</summary>{open && children}</details>;
}

function PolicyDetails({ offering, user }) {
  const resource = useRemote(signal => apiRequest(`${root}offerings/${offering}/eligibility/`, { signal }), [offering]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const key = useRef(null);
  async function save(event, exception = false) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const body = exception ? { student: data.get('student'), enabled: data.get('enabled') === 'on', reason: data.get('reason') }
      : { minimum_percentage: data.get('minimum_percentage'), reason: data.get('reason') };
    setBusy(true); setError('');
    try { await apiRequest(`${root}offerings/${offering}/${exception ? 'exam-exceptions' : 'eligibility'}/`, { method: exception ? 'POST' : 'PUT', body: eventPayload(key, body) }); key.current = null; resource.reload(); }
    catch (err) { setError(`${err.message} Refresh the saved decisions before retrying an uncertain action.`); } finally { setBusy(false); }
  }
  return <><p>Exam restrictions use only current finalised meetings. Zero eligible meetings or no threshold means unknown, not failure. Excused meetings are excluded.</p><Alert>{error}</Alert><button onClick={resource.reload}>Refresh exam attendance</button><RemoteState resource={resource}>{rows => <>
    {!rows.length ? <Empty>No students are currently available for this course.</Empty> : <Table headings={['Student', 'Finalised attendance', 'Eligible meetings', 'Pending meetings', 'Excused', 'Threshold', 'Exam decision']}>
      {rows.map(row => <tr key={row.student_id}><td>{row.full_name} · {row.identifier_value}</td><td>{row.rate_percent === null ? 'Unknown' : `${row.rate_percent}%`}</td><td>{row.eligible_recorded_meetings}</td><td>{row.pending_meetings}</td><td>{row.excused_meetings} ({row.retrospective_excused_meetings} retrospective)</td><td>{row.threshold ?? 'Not set'}</td><td>{row.exam_status.replaceAll('_',' ')}{row.exception_reason && <p>{row.exception_reason}</p>}</td></tr>)}</Table>}
    {hasPermission(user, 'attendance.correct_attendance') && <><form className="live-form" onSubmit={event => save(event)}><h3>Set course threshold</h3><label>Required attendance percentage<input type="number" name="minimum_percentage" min="0" max="100" step="0.01" required disabled={busy} /></label><label>Written policy reason<input name="reason" maxLength={1000} required disabled={busy} /></label><button disabled={busy}>Save threshold decision</button></form>
      <form className="live-form" onSubmit={event => save(event, true)}><h3>Grant or revoke an exam exception</h3><label>Student<select name="student" required disabled={busy}><option value="">Choose a student</option>{rows.map(row => <option key={row.student_id} value={row.student_id}>{row.full_name} · {row.identifier_value}</option>)}</select></label><label><input name="enabled" type="checkbox" defaultChecked disabled={busy} /> Exception approved (clear to revoke)</label><label>Written exception reason<input name="reason" required maxLength={1000} disabled={busy} /></label><button disabled={busy}>Save audited exam exception</button></form></>}
  </>}</RemoteState></>;
}
function CoursePolicyContent({ user }) {
  const resource = useRemote(signal => apiRequest('/api/teaching/courses/', { signal }), []);
  const [offering, setOffering] = useState('');
  return <RemoteState resource={resource}>{courses => <><label>Course<select value={offering} onChange={event => setOffering(event.target.value)}><option value="">Choose an assigned course</option>{courses.map(row => <option key={row.id} value={row.id}>{row.course} · {row.session} · {row.semester}</option>)}</select></label>{offering && <PolicyDetails key={offering} offering={offering} user={user} />}</>}</RemoteState>;
}
export function CoursePolicy({ user }) { return <Expand title="Course attendance thresholds and exam decisions"><CoursePolicyContent user={user} /></Expand>; }

function StudentEligibilityContent() {
  const resource = useRemote(signal => apiRequest('/api/me/attendance-eligibility/', { signal }), []);
  return <><p>These decisions use only finalised meetings and your formal excuses. Unknown means there is insufficient finalised data or no threshold; it does not mean restricted.</p><RemoteState resource={resource}>{rows => !rows.length ? <Empty>No exam attendance decisions are available yet.</Empty> : <Table headings={['Course', 'Finalised attendance', 'Pending', 'Excused', 'Exam decision']}>
    {rows.map(row => <tr key={row.offering_id}><td>{row.course}</td><td>{row.rate_percent === null ? 'Unknown' : `${row.rate_percent}%`}</td><td>{row.pending_meetings}</td><td>{row.excused_meetings}</td><td>{row.exam_status.replaceAll('_',' ')}</td></tr>)}</Table>}</RemoteState></>;
}
export function StudentEligibility() { return <Expand title="Review my exam attendance eligibility"><StudentEligibilityContent /></Expand>; }

function MeetingReviewContent({ session, user, onSaved }) {
  const canCorrect = hasPermission(user, 'attendance.correct_attendance'), canImport = hasPermission(user, 'attendance.import_pending_captures');
  const state = useRemote(signal => canCorrect ? apiRequest(`${root}sessions/${session.id}/finalisation/`, { signal }) : Promise.resolve(null), [session.id, canCorrect]);
  const captures = useRemote(async signal => {
    if (!canImport) return [];
    const rows = []; let next = `${root}sessions/${session.id}/captures/`;
    for (let page = 1; next && page <= 500; page += 1) { const data = await apiRequest(`${root}sessions/${session.id}/captures/`, { query: { page }, signal }); rows.push(...data.results); next = data.next; }
    return rows;
  }, [session.id, canImport]);
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [selected, setSelected] = useState('');
  const key = useRef(null);
  const [reviewModes, setReviewModes] = useState({});
  const historical = session.student_details || session.student_ids.map(id => ({ id, full_name: id }));
  const students = [...new Map([...historical, ...(session.current_roster_students || [])].map(row => [row.id, row])).values()];
  async function act(path, body, idempotent = false) {
    setBusy(true); setError(''); setNotice('');
    try { await apiRequest(path, { method: 'POST', body: idempotent ? eventPayload(key, body) : body }); key.current = null; state.reload(); captures.reload(); onSaved?.(); setNotice('The reviewed attendance decision was saved.'); }
    catch (err) { setError(`${err.message} Refresh the review before retrying an uncertain decision.`); } finally { setBusy(false); }
  }
  async function excuse(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    await act(`${root}sessions/${session.id}/excusals/`, { student: data.get('student'), is_excused: data.get('is_excused') === 'on', retrospective: data.get('retrospective') === 'on', reason: data.get('reason') }, true);
  }
  async function resolve(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    await act(`${root}captures/${selected}/resolve/`, { student: data.get('student'), reason: data.get('reason'), timing_confirmed: data.get('timing') === 'on' });
  }
  return <><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}{canCorrect && <RemoteState resource={state}>{data => data && <>
    <p>Collection: {data.collection_status} · {data.finalised ? 'Reviewed and finalised' : data.review_stale ? 'Source evidence changed: review again' : 'Not finalised'} · Review revision {data.revision}</p><button onClick={state.reload}>Refresh evidence and confirmed records</button>
    <Table headings={['Confirmed student', 'Status']}>{data.confirmed_records.map(row => <tr key={row.record_id}><td>{historical.find(student => student.id === row.student_id)?.full_name || row.student_id}</td><td>{row.status}</td></tr>)}</Table>
    <p>Archived captures remain intact when the meeting is finalised. Finalisation permits rates from confirmed records without automatically identifying unknown captures.</p>
    {session.status === 'closed' && <form className="live-form" onSubmit={event => { event.preventDefault(); const fields = new FormData(event.currentTarget); act(`${root}sessions/${session.id}/finalisation/`, { expected_digest: data.review_sha256, reviewed: fields.get('reviewed') === 'on', reason: fields.get('reason') }); }}><label>Written finalisation reason<input name="reason" required maxLength={1000} disabled={busy} /></label><label><input name="reviewed" type="checkbox" required disabled={busy} /> I reviewed confirmed records, formal excuses and retained unmatched evidence for this meeting.</label><button disabled={busy}>Finalise this reviewed meeting</button></form>}
    <h3>Formal excuses</h3>{data.confirmed_excusals.map(row => <p key={row.student_id}>{students.find(student => student.id === row.student_id)?.full_name || row.student_id} · {row.is_excused ? 'Excused' : 'Excuse revoked'}{row.retrospective && ' · Retrospective late-registration exception'} · {row.reason}</p>)}
    <form className="live-form" onSubmit={excuse}><label>Student<select name="student" required disabled={busy}><option value="">Choose a student</option>{students.map(row => <option key={row.id} value={row.id}>{row.full_name} · {row.identifier_value || ''}</option>)}</select></label><label><input name="is_excused" type="checkbox" defaultChecked disabled={busy} /> Formal excuse approved (clear to revoke)</label><label><input name="retrospective" type="checkbox" disabled={busy} /> Retrospective excuse for a later-registered student outside this meeting roster</label><label>Written excuse reason<input name="reason" maxLength={1000} required disabled={busy} /></label><button disabled={busy}>Save formal excuse decision</button></form>
  </>}</RemoteState>}
    {canImport && <RemoteState resource={captures}>{rows => <><h3>Retained fingerprint captures</h3>{!rows.length ? <Empty>No captured probes have been imported.</Empty> : rows.map((row,index) => <p key={row.capture_id}>Capture {index+1} · {row.state} · {row.mode} {!row.review_selected && <label>Review context<select value={reviewModes[row.capture_id] || row.mode || 'deferred'} onChange={event => setReviewModes(old => ({ ...old, [row.capture_id]: event.target.value }))}><option value="deferred">Deferred capture archive</option><option value="live">Live capture flagged review</option></select></label>} {row.state !== 'resolved' && <button disabled={busy} onClick={async () => { await act(`${root}captures/${row.capture_id}/review/`, { mode: reviewModes[row.capture_id] || row.mode || 'deferred' }); setSelected(row.capture_id); }}>Choose for staff review</button>}</p>)}
      {selected && canCorrect && <form className="live-form" onSubmit={resolve}><h4>Resolve selected capture using reviewed identity evidence</h4><label>Student<select name="student" required>{historical.map(row => <option key={row.id} value={row.id}>{row.full_name} · {row.identifier_value || ''}</option>)}</select></label><label><input type="checkbox" name="timing" required /> I verified this capture belongs to this meeting; boot elapsed time is not a wall-clock date.</label><label>Identity evidence and written reason<input name="reason" maxLength={1000} required /></label><button disabled={busy}>Confirm student presence from reviewed evidence</button></form>}
    </>}</RemoteState>}
  </>;
}
export function MeetingReview(props) { return <Expand title="Review captures, formal excuses and finalise attendance"><MeetingReviewContent {...props} /></Expand>; }

function ReferenceContent() {
  const references = useRemote(signal => apiRequest(`${root}biometric-references/`, { signal }), []);
  const students = useRemote(signal => apiRequest(`${root}biometric-students/`, { signal }), []);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function enrol(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget), body = { student: data.get('student'), scanner_uuid: data.get('scanner_uuid'), reference_id: data.get('reference_id') };
    if (data.get('replaces')) body.replaces = Number(data.get('replaces'));
    setBusy(true); setError('');
    try { await apiRequest(`${root}biometric-references/`, { method: 'POST', body }); references.reload(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <><p>Enrol the finger on the configured scanner first, then link its reference here. This records the student mapping; it does not remotely enrol or match a finger. Replacement disables the old reference and preserves its history.</p><Alert>{error}</Alert><RemoteState resource={students}>{rows => <RemoteState resource={references}>{refs => <><form className="live-form" onSubmit={enrol}><label>Student<select name="student" required>{rows.map(row => <option key={row.id || row.student_id} value={row.id || row.student_id}>{row.full_name} · {row.identifier_value}</option>)}</select></label><label>Configured scanner UUID<input name="scanner_uuid" required /></label><label>Enrolled scanner reference / slot<input name="reference_id" required maxLength={100} /></label><label>Replace an existing reference (optional)<select name="replaces"><option value="">New enrolment mapping</option>{refs.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{rows.find(student => (student.id || student.student_id) === row.student_id)?.full_name || row.student_id} · Scanner reference {row.reference_id}</option>)}</select></label><button disabled={busy}>Save scanner reference mapping</button></form><Table headings={['Student', 'Scanner reference', 'Status']} >{refs.map(row => <tr key={row.id}><td>{rows.find(student => (student.id || student.student_id) === row.student_id)?.full_name || row.student_id}</td><td>{row.reference_id}</td><td>{row.is_active ? 'Active' : `Disabled ${formatDate(row.disabled_at)}`}</td></tr>)}</Table></>}</RemoteState>}</RemoteState></>;
}
export function BiometricReferences() { return <Expand title="Student fingerprint enrolment and replacement"><ReferenceContent /></Expand>; }
