import SourceComparisons from './SourceComparisons';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import * as api from '../api';
import { Alert, Empty, Pager, RemoteState, Table } from './ui';
import { formatDate, hasPermission, useRemote } from './resources';
import StudentRegistration, { PromoteIdentifier, StudentProfileEditor } from './StudentRegistration';
import StudentLogin from './StudentLogin';
import DocumentUpload from '../pages/DocumentUpload';

function Profile({ row }) {
  return <dl className="live-details">{[
    ['Full name', row.full_name], ['Student identifier', row.identifier_value], ['Student record ID', row.student_id],
    ['Level', row.current_level], ['Admission year', row.admission_year], ['Admission mode', row.mode_of_admission],
    ['Phone number', row.phone_number], ['Academic status', row.academic_status], ['Active', row.is_active ? 'Yes' : 'No'],
  ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Not recorded'}</dd></div>)}</dl>;
}

function MyProfile() {
  const resource = useRemote(api.getMyStudentProfile, []);
  return <section className="live-card"><h2>My student profile</h2><RemoteState resource={resource}>{(row) => <Profile row={row} />}</RemoteState>
    <p className="live-hint">Contact your adviser if a profile detail needs correction.</p></section>;
}

function GuardianEditor({ studentId, row, onSaved }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget, body = Object.fromEntries(new FormData(form));
    setBusy(true); setError('');
    try {
      if (row) await api.updateGuardian(studentId, row.guardian_id, body);
      else await api.createGuardian(studentId, body);
      form.reset(); onSaved();
    } catch (err) { setError(`${err.message} Refresh guardian records before retrying a request with an uncertain outcome.`); }
    finally { setBusy(false); }
  }
  return <details><summary>{row ? `Edit ${row.full_name}` : 'Add a guardian'}</summary><Alert>{error}</Alert>
    <form className="live-form" onSubmit={submit}>{[['full_name', 'Full name', 'text'], ['relationship', 'Relationship', 'text'], ['email', 'Email', 'email'], ['phone_number', 'Phone number', 'tel'], ['address', 'Address', 'text']].map(([name, label, type]) => <label key={name}>{label}<input name={name} type={type} defaultValue={row?.[name] || ''} required={['full_name', 'relationship'].includes(name)} disabled={busy} /></label>)}
      <button disabled={busy} className="live-primary">{busy ? 'Saving…' : 'Save guardian'}</button></form></details>;
}

function StudentDetail({ studentId, user, onClose }) {
  const [page, setPage] = useState(1), [notice, setNotice] = useState('');
  const profile = useRemote((signal) => api.getStudent(studentId, signal), [studentId]);
  const canRead = hasPermission(user, 'students.view_guardian');
  const guardians = useRemote((signal) => canRead ? api.listGuardians(studentId, page, signal) : Promise.resolve(null), [studentId, page, canRead]);
  function saved() { setNotice('Guardian details saved. Review result-sharing consent separately before sending.'); guardians.reload(); }
  return <section className="live-card"><div className="live-row"><h2>Student record</h2><button onClick={onClose}>Close record</button></div>
    <RemoteState resource={profile}>{(row) => <><Profile row={row} /><StudentProfileEditor row={row} user={user} onSaved={profile.reload} /><PromoteIdentifier key={`promote:${row.identifier_value}`} row={row} user={user} onSaved={profile.reload} /><StudentLogin studentId={row.student_id} identifierValue={row.identifier_value} identifierType={row.identifier_type} user={user} studentActive={row.is_active} />{hasPermission(user, 'documents.add_studentdocument') && <DocumentUpload key={`documents:${row.student_id}`} studentId={row.student_id} />}</>}</RemoteState>
    {canRead && <><h3>Guardians</h3>{notice && <p role="status">{notice}</p>}<RemoteState resource={guardians}>{(data) => <>
      {!data.results.length && <Empty>No guardians have been recorded.</Empty>}
      {data.results.map((row) => <article key={row.guardian_id} className="live-inset"><h4>{row.full_name}</h4><p>{row.relationship} · {row.email || 'No email'} · {row.phone_number || 'No phone'}</p>
        {hasPermission(user, 'students.change_guardian') && <GuardianEditor studentId={studentId} row={row} onSaved={saved} />}</article>)}
      <Pager page={page} data={data} onChange={setPage} />
    </>}</RemoteState>{hasPermission(user, 'students.add_guardian') && <GuardianEditor studentId={studentId} onSaved={saved} />}</>}
  </section>;
}

function Students({ user }) {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState({ search: '', current_level: '' }), [page, setPage] = useState(1), [studentId, setStudentId] = useState(searchParams.get('student'));
  const resource = useRemote((signal) => api.listStudents({ ...query, page }, signal), [query.search, query.current_level, page]);
  function search(event) { event.preventDefault(); setQuery(Object.fromEntries(new FormData(event.currentTarget))); setPage(1); setStudentId(null); }
  return <><StudentRegistration user={user} initialIdentifier={searchParams.get('register') || ''} initialIdentifierType={searchParams.get('identifier_type')} onCreated={(row) => { setStudentId(row.student_id); resource.reload(); }} /><section className="live-card"><h2>Student directory</h2><p>Search the student records available to your account.</p>
    <form className="live-filters" onSubmit={search}><label>Search name or identifier<input name="search" type="search" /></label><label>Level<input name="current_level" type="number" min="1" /></label><button className="live-primary">Search students</button></form>
    <RemoteState resource={resource}>{(data) => <>{!data.results.length ? <Empty>No students match these filters.</Empty> : <Table headings={['Name', 'Identifier', 'Level', 'Status', 'Record']}>
      {data.results.map((row) => <tr key={row.student_id}><td>{row.full_name}</td><td>{row.identifier_value}</td><td>{row.current_level}</td><td>{row.academic_status}</td><td><button onClick={() => setStudentId(row.student_id)}>View {row.full_name}</button></td></tr>)}</Table>}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState>
  </section>{studentId && <StudentDetail key={studentId} studentId={studentId} user={user} onClose={() => setStudentId(null)} />}</>;
}

function ResultActions({ row, user, onSaved }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    const values = new FormData(event.currentTarget), action = event.nativeEvent.submitter?.value;
    setBusy(true); setError('');
    try {
      if (action === 'verify') await api.verifyResult(row.id, row.score);
      else await api.updateResultScore(row.id, values.get('score') === '' ? null : values.get('score'));
      onSaved();
    } catch (err) { setError(`${err.message} Refresh results before retrying if the outcome is uncertain.`); }
    finally { setBusy(false); }
  }
  return <details><summary>Review result {row.id}</summary><Alert>{error}</Alert><form className="live-form" onSubmit={save}>
    {hasPermission(user, 'academics.change_result') && <><label>Corrected score (blank clears it)<input name="score" type="number" min="0" max="100" step="0.01" defaultValue={row.score ?? ''} disabled={busy} /></label><button value="save" disabled={busy}>Save score correction</button></>}
    {!row.is_verified && row.score !== null && hasPermission(user, 'academics.verify_result') && <><p>Verify the currently displayed score: <strong>{row.score}</strong>.</p><button name="action" value="verify" disabled={busy}>Verify displayed score {row.score}</button></>}
  </form></details>;
}

function CreateResult({ onSaved }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); const form = event.currentTarget, values = Object.fromEntries(new FormData(form));
    setBusy(true); setError('');
    try { await api.createResult({ ...values, offering_id: Number(values.offering_id), attempt_number: Number(values.attempt_number), score: values.score === '' ? null : values.score }); form.reset(); onSaved(); }
    catch (err) { setError(`${err.message} Check the result list before retrying an uncertain request.`); }
    finally { setBusy(false); }
  }
  return <details><summary>Add an unverified result</summary><Alert>{error}</Alert><form className="live-form" onSubmit={submit}>
    <label>Student record ID<input name="student_id" required disabled={busy} /></label><label>Course offering ID<input name="offering_id" type="number" min="1" required disabled={busy} /></label>
    <label>Attempt number<input name="attempt_number" type="number" min="1" defaultValue="1" required disabled={busy} /></label><label>Score (optional)<input name="score" type="number" min="0" max="100" step="0.01" disabled={busy} /></label>
    <p className="live-hint">Use the student record ID from the directory and the offering ID configured by the HOD. New records require separate verification.</p><button disabled={busy} className="live-primary">{busy ? 'Saving…' : 'Create result'}</button></form></details>;
}

function MyAverage() {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [data, setData] = useState(null);
  async function submit(event) {
    event.preventDefault(); const values = new FormData(event.currentTarget); setBusy(true); setError(''); setData(null);
    try { const [gpa, cgpa] = await Promise.all([api.getMyGpa(values.get('session'), values.get('semester')), api.getMyCgpa()]); setData({ gpa, cgpa }); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <details><summary>Calculate my GPA and CGPA</summary><Alert>{error}</Alert><form className="live-filters" onSubmit={submit}>
    <label>Academic session<input name="session" pattern="[0-9]{4}/[0-9]{4}" placeholder="2025/2026" required disabled={busy} /></label><label>Semester<select name="semester" disabled={busy}><option value="harmattan">Harmattan</option><option value="rain">Rain</option></select></label>
    <button disabled={busy}>Calculate averages</button></form>{data && <><p role="status"><strong>System-calculated GPA: {data.gpa.gpa ?? 'No results'} | System-calculated CGPA: {data.cgpa.cgpa ?? 'No results'}</strong> | History: {data.cgpa.history_completeness.replaceAll('_', ' ')}</p><SourceComparisons reports={data.cgpa.source_reports || data.gpa.source_reports} /></>}</details>;
}

function Results({ user }) {
  const student = user.role === 'student';
  const [page, setPage] = useState(1), [filters, setFilters] = useState({});
  const resource = useRemote((signal) => student ? api.listMyResults(page, signal) : api.listResults({ ...filters, page }, signal), [page, student, filters]);
  function search(event) { event.preventDefault(); setFilters(Object.fromEntries(new FormData(event.currentTarget))); setPage(1); }
  return <section className="live-card"><h2>{student ? 'My verified results' : 'Result review'}</h2><p>{student ? 'Your verified results are returned by the student service.' : 'Results are restricted to your assigned students. A score correction removes verification until it is reviewed again.'}</p>
    {!student && <form className="live-filters" onSubmit={search}><label>Student record ID<input name="student_id" /></label><label>Academic session<input name="academic_session" placeholder="2025/2026" pattern="[0-9]{4}/[0-9]{4}" /></label>
      <label>Semester<select name="semester"><option value="">All semesters</option><option value="harmattan">Harmattan</option><option value="rain">Rain</option></select></label><button>Filter results</button></form>}
    <RemoteState resource={resource}>{(data) => <>{!data.results.length ? <Empty>No results are available for this selection.</Empty> : <Table headings={['Result', ...(student ? [] : ['Student record ID']), 'Offering ID', 'Attempt', 'Score', 'Units', 'Verification', ...(!student ? ['Review'] : [])]}>
      {data.results.map((row) => <tr key={row.id}><td>{row.id}</td>{!student && <td>{row.student}</td>}<td>{row.offering}</td><td>{row.attempt_number}</td><td>{row.score ?? 'Not scored'}</td><td>{row.credit_units}</td><td>{row.is_verified ? 'Verified' : 'Awaiting review'}</td>
        {!student && <td>{(hasPermission(user, 'academics.change_result') || hasPermission(user, 'academics.verify_result')) && <ResultActions row={row} user={user} onSaved={resource.reload} />}</td>}</tr>)}</Table>}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState>
    {student ? <MyAverage /> : hasPermission(user, 'academics.add_result') && <CreateResult onSaved={resource.reload} />}
  </section>;
}

function Messages() {
  const [page, setPage] = useState(1), [source, setSource] = useState('adviser');
  const resource = useRemote((signal) => source === 'adviser' ? api.listMyAdviserMessages(page, signal) : api.listMyHodMessages(page, signal), [page, source]);
  return <section className="live-card"><h2>Department messages</h2><label>Message source<select value={source} onChange={(event) => { setSource(event.target.value); setPage(1); }}><option value="adviser">Adviser</option><option value="hod">Head of Department</option></select></label>
    <RemoteState resource={resource}>{(data) => <>{!data.results.length && <Empty>No messages have been received.</Empty>}{data.results.map((row) => <article key={row.id} className="live-inset"><h3>{row.subject}</h3><p className="live-hint">{row.sender_name} · {formatDate(row.created_at)}</p><p className="live-message">{row.body}</p></article>)}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState></section>;
}

export default function Records({ section, user }) {
  if (section === 'profile') return <MyProfile />;
  if (section === 'students') return <Students user={user} />;
  if (section === 'results') return <Results user={user} />;
  return <Messages />;
}
