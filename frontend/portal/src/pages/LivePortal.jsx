import { useCallback, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { changePassword, getMyStudentProfile, getStudent, listMyResults, listStudents } from '../api';
import { useAuth } from '../auth/useAuth';
import { hasPermission, workspaceHome, workspaceRoles } from '../auth/permissions';
import { LoadState, Pager, ProfileFields } from '../components/LiveData';
import { useRemote } from '../useRemote';
import { Workspace as GuardianWorkspace } from '../guardian/App';
import { guardianClient } from '../guardian/client';
import '../guardian/styles.css';
import DocumentUpload from './DocumentUpload';

function OwnProfile() {
  const resource = useRemote(getMyStudentProfile);
  return <LoadState resource={resource}>{student => <ProfileFields student={student} />}</LoadState>;
}

function OwnResults() {
  const [page, setPage] = useState(1);
  const load = useCallback(signal => listMyResults(page, signal), [page]);
  const resource = useRemote(load);
  return <LoadState resource={resource}>{data => <>{data.results.length ? <div className="live-table"><table><thead><tr><th>Offering</th><th>Attempt</th><th>Score</th><th>Units</th><th>Verification</th></tr></thead><tbody>{data.results.map(row => <tr key={row.id}><td>{row.offering}</td><td>{row.attempt_number}</td><td>{row.score ?? 'Not recorded'}</td><td>{row.credit_units}</td><td>{row.is_verified ? 'Verified' : 'Unverified'}</td></tr>)}</tbody></table></div> : <p>No verified results are available.</p>}<Pager data={data} page={page} onChange={setPage} /></>}</LoadState>;
}

function StudentDetail({ id }) {
  const { user } = useAuth();
  const load = useCallback(signal => getStudent(id, signal), [id]);
  const resource = useRemote(load);
  return <LoadState resource={resource}>{student => <><ProfileFields student={student} />{hasPermission(user, 'documents.add_studentdocument') && <DocumentUpload studentId={student.student_id} />}</>}</LoadState>;
}

function Students() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const load = useCallback(signal => listStudents({ search, page }, signal), [search, page]);
  const resource = useRemote(load);
  return <><label>Search student records<input type="search" value={search} onChange={event => { setSearch(event.target.value); setPage(1); setSelected(null); }} /></label>
    <LoadState resource={resource}>{data => <>{data.results.length ? <div className="live-table"><table><thead><tr><th>Student</th><th>Identifier</th><th>Level</th></tr></thead><tbody>{data.results.map(row => <tr key={row.student_id}><td><button onClick={() => setSelected(row.student_id)}>{row.full_name}</button></td><td>{row.identifier_value}</td><td>{row.current_level}</td></tr>)}</tbody></table></div> : <p>No students match this search in your permitted scope.</p>}<Pager data={data} page={page} onChange={value => { setPage(value); setSelected(null); }} /></>}</LoadState>
    {selected && <section className="live-card"><h2>Student profile</h2><StudentDetail key={selected} id={selected} /></section>}</>;
}

function PasswordChange() {
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try { await changePassword(current, password); setCurrent(''); setPassword(''); setMessage('Password changed.'); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit}>{error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <label>Current password<input type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} required disabled={busy} /></label>
    <label>New password<input type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} required disabled={busy} /></label><button disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button></form>;
}

export default function LivePortal() {
  const { user, signOut } = useAuth();
  const { role, section = 'dashboard' } = useParams();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const roles = workspaceRoles(user);
  if (!roles.includes(role)) return <Navigate to={workspaceHome(user)} replace />;
  const student = user.role === 'student';
  const menu = [['dashboard', 'Dashboard'], ['profile', student ? 'My student profile' : 'My account'], ['password', 'Change password']];
  if (student) menu.push(['results', 'My results']);
  if (user.is_staff && hasPermission(user, 'students.view_student')) menu.push(['students', 'Student records']);
  if (user.role === 'hod' && user.is_staff && user.is_superuser) menu.push(['guardian-results', 'Guardian results']);
  async function logout() {
    if (busy) return;
    setBusy(true); setError('');
    try { await signOut(); navigate('/login', { replace: true }); }
    catch (failure) { setError(failure.message || 'Unable to sign out. Try again.'); }
    finally { setBusy(false); }
  }
  const available = menu.some(([key]) => key === section);
  return <main className="live-portal"><header className="live-heading"><div><p>EEE OAU · {role === 'adviser' ? 'Part adviser' : user.role}</p><h1>{user.first_name || user.username}’s workspace</h1></div><button onClick={logout} disabled={busy}>{busy ? 'Signing out…' : 'Log out'}</button></header>
    {error && <p role="alert">{error}</p>}
    <nav className="live-actions" aria-label="Account workspace">{menu.map(([key, label]) => <Link key={key} aria-current={section === key ? 'page' : undefined} to={`/portal/${role}/${key}`}>{label}</Link>)}
      {roles.length > 1 && <Link to={`/portal/${role === 'adviser' ? 'staff' : 'adviser'}/dashboard`}>{role === 'adviser' ? 'Teaching workspace' : 'Adviser workspace'}</Link>}
      {user.is_staff && hasPermission(user, 'attendance.view_attendance') && <Link to="/attendance">Class attendance</Link>}
    </nav>
    <section className="live-card" key={`${user.id}-${role}-${section}`}>
      {!available ? <><h2>This feature is not connected yet</h2><p>Choose an available page above. Prototype workflows can be explored separately in the <Link to={`/demo/${role}/dashboard`}>demo</Link>.</p></> :
        section === 'dashboard' ? <><h2>Signed in as {user.username}</h2><p>This workspace uses your departmental account and the records the server permits you to access.</p>{role === 'adviser' && <p>Assigned adviser levels: {user.adviser_levels.join(', ')}</p>}<p>Select a page to view current records.</p></> :
          section === 'profile' ? student ? <OwnProfile /> : <dl className="live-fields">{[['Username', user.username], ['Name', `${user.first_name} ${user.last_name}`.trim()], ['Email', user.email]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Not recorded'}</dd></div>)}</dl> :
            section === 'students' ? <Students /> : section === 'results' ? <OwnResults /> : section === 'guardian-results' ? <div className="guardian-results"><h2>Guardian results</h2><GuardianWorkspace api={guardianClient} /></div> : <PasswordChange />}
    </section>
  </main>;
}
