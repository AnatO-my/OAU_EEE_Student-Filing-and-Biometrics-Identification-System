import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { Alert, PortalIcon } from './ui';
import { hasPermission, isHod } from './resources';
import Records from './Records';
import Attendance from './Attendance';
import AcademicSession from './AcademicSession';
import './live.css';

const GuardianResults = lazy(() => import('./GuardianResults'));
const RecordImports = lazy(() => import('./RecordImports'));
const AccountSettings = lazy(() => import('./AccountSettings'));
const Teaching = lazy(() => import('./Teaching'));
const Courses = lazy(() => import('./Courses'));
const StudentRecordsBatch = lazy(() => import('./StudentRecordsBatch'));
const ForcedPasswordChange = lazy(() => import('./ForcedPasswordChange'));

const workspaceDetails = {
  dashboard: ['Your department, in one place.', 'Choose a workspace to continue with your academic records.'],
  students: ['Student records', 'Find a student, register a new arrival or complete their details.'],
  profile: ['Your student record', 'Review your personal and academic registration details.'],
  results: ['Academic results', 'Review course scores, verification and academic progress.'],
  imports: ['From mark sheet to results', 'Convert your sheet, review matched scores and save approved results.'],
  courses: ['Courses and teaching assignments', 'Create catalogue courses, offer them for a semester and assign teaching staff.'],
  attendance: ['Class attendance', 'Review the classes and attendance records available to your account.'],
  messages: ['Department messages', 'Read announcements and follow updates from your department.'],
  materials: ['Course materials', 'Find the teaching materials available for your courses.'],
  timetable: ['Course timetable', 'Review scheduled classes and any student timetable clashes.'],
  workflows: ['Documents and requests', 'Manage student documents, correction requests and account administration.'],
  'earlier-messages': ['Earlier messages', 'Read messages sent through the earlier department inbox.'],
  'guardian-results': ['Guardian communication', 'Review consent and result reports before sharing them.'],
  'academic-session': ['Academic session', 'Manage the current period used for staff assignments and attendance.'],
  account: ['Account settings', 'Manage the password you use to access your department portal.'],
};

const tileDescriptions = {
  students: 'Find a record or register a student.', profile: 'Your registration and contact details.',
  results: 'Course scores and academic progress.', imports: 'Convert a mark sheet and review scores.',
  courses: 'Course catalogue, semester offerings and teaching staff.',
  attendance: 'Classes, rosters and attendance records.', messages: 'Messages from your department.',
  materials: 'Teaching materials and earlier versions.', timetable: 'Scheduled classes and clash warnings.',
  workflows: 'Document history, approvals and student requests.', 'earlier-messages': 'Your earlier department inbox.',
  'guardian-results': 'Consent, reports and delivery history.', 'academic-session': 'The current academic period.',
};

export default function LivePortal() {
  const { user, status, error, refreshUser, signOut } = useAuth();
  const { role, section = 'dashboard' } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutError, setLogoutError] = useState('');
  const [busy, setBusy] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const navigationToggle = useRef(null);
  const userId = user?.id;
  useEffect(() => {
    if (status !== 'ready' || !userId) return;
    const main = document.getElementById('portal-main');
    main?.focus({ preventScroll: true });
    main?.scrollIntoView?.({ block: 'start', behavior: 'instant' });
  }, [section, role, status, userId]);

  if (status === 'loading') return <main className="live-session" role="status">Checking your session…</main>;
  if (status === 'error') return <main className="live-session"><Alert>{error?.message || 'Unable to check your session.'}</Alert><button onClick={() => refreshUser().catch(() => {})}>Retry session check</button></main>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />;
  if (user.must_change_password) return <Suspense fallback={<p role="status">Loading password setup…</p>}><ForcedPasswordChange /></Suspense>;
  if (!['hod', 'staff', 'student'].includes(user.role)) return <Navigate to="/access-denied" replace />;
  if (role !== user.role) return <Navigate to={`/portal/${user.role}/${section === 'account' ? 'account' : 'dashboard'}`} replace />;

  const student = user.role === 'student';
  const links = [['dashboard', 'Overview']];
  if (student) links.push(['profile', 'My profile'], ['results', 'My results'], ['messages', 'Messages'], ['attendance', 'My attendance']);
  else {
    if (hasPermission(user, 'students.view_student')) links.push(['students', 'Students']);
    if (hasPermission(user, 'students.view_student') && hasPermission(user, 'academics.view_result')) links.push(['results', 'Results']);
    if ((isHod(user) || user.adviser_levels?.length) && hasPermission(user, 'students.view_student') && hasPermission(user, 'academics.view_result') && hasPermission(user, 'academics.add_result')) links.push(['imports', 'Upload results']);
    if (hasPermission(user, 'attendance.view_attendance') || hasPermission(user, 'attendance.manage_biometric_reference')) links.push(['attendance', 'Attendance']);
    if (isHod(user)) links.push(['courses', 'Courses'], ['guardian-results', 'Guardian results'], ['academic-session', 'Academic session']);
  }
  if (!student) links.push(['messages', 'Messages']);
  links.push(['materials', 'Course materials'], ['timetable', 'Timetable'], ['workflows', 'Documents and requests']);
  if (student) links.push(['earlier-messages', 'Earlier messages']);
  const title = section === 'account' ? 'Account settings' : links.find(([key]) => key === section)?.[1];
  const roleTitle = isHod(user) ? 'Head of Department' : student ? 'Student' : 'Staff';
  const displayName = user.first_name || user.username;
  const initials = displayName.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  async function logout() {
    setBusy(true); setLogoutError('');
    try { await signOut(); navigate('/login', { replace: true }); }
    catch (err) { setLogoutError(err.message); }
    finally { setBusy(false); }
  }
  return <div className="live-app"><a className="live-skip" href="#portal-main" onClick={(event) => { event.preventDefault(); document.getElementById('portal-main')?.focus(); }}>Skip to main content</a>
    <aside className="live-sidebar" onKeyDown={(event) => { if (event.key === 'Escape' && navigationOpen) { setNavigationOpen(false); navigationToggle.current?.focus(); } }}><div className="live-brand-row"><Link className="live-brand" to="/"><span className="live-brand-mark"><PortalIcon name="brand" /></span><span>EEE <b>OAU</b><small>Department portal</small></span></Link>
      <button className="live-nav-toggle" ref={navigationToggle} aria-expanded={navigationOpen} aria-controls="portal-navigation" onClick={() => setNavigationOpen((open) => !open)}>{navigationOpen ? 'Close menu' : 'Menu'}</button></div>
    <p className="live-nav-label">Workspace</p><nav id="portal-navigation" aria-label="Portal navigation" data-open={navigationOpen}>{links.map(([key, label]) => <Link key={key} to={`/portal/${user.role}/${key}`} aria-current={section === key ? 'page' : undefined} onClick={() => { setNavigationOpen(false); if (navigationOpen) document.getElementById('portal-main')?.focus(); }}><PortalIcon name={key} /><span>{label}</span>{section === key && <span className="live-nav-current" aria-hidden="true" />}</Link>)}</nav>
    <div className="live-identity"><div className="live-identity-person"><span className="live-avatar" aria-hidden="true">{initials}</span><div><strong>{displayName}</strong><small>{roleTitle}</small></div></div>
      <Link className="live-account-link" to={`/portal/${user.role}/account`} aria-current={section === 'account' ? 'page' : undefined} onClick={() => { setNavigationOpen(false); if (navigationOpen) document.getElementById('portal-main')?.focus(); }}><PortalIcon name="account" /><span>Account settings</span>{section === 'account' && <span className="live-nav-current" aria-hidden="true" />}</Link>
      {!!user.adviser_levels?.length && <small className="live-adviser-scope">Adviser · {user.adviser_levels.join(', ')} level</small>}
      <button disabled={busy} onClick={logout}><PortalIcon name="logout" />{busy ? 'Signing out…' : 'Sign out'}</button><Alert>{logoutError}</Alert></div></aside>
    <main className="live-main" id="portal-main" tabIndex={-1}><header className="live-page-title"><div className="live-page-topline"><p className="live-kicker">Electrical &amp; Electronic Engineering</p><span className="live-role-pill">{roleTitle}</span></div><h1>{title || 'Access restricted'}</h1><p>{section === 'account' && isHod(user) ? 'Manage your password, department ownership and staff assignments.' : title ? workspaceDetails[section]?.[1] : 'Choose a workspace available to your account.'}</p></header>
      {!title ? <section className="live-card"><h2>This section is unavailable</h2><p>Choose one of the workspaces available to your account.</p></section> : <Suspense fallback={<p role="status">Loading workspace…</p>}>
        {section === 'dashboard' && <div className="live-overview"><section className="live-welcome"><div><p className="live-kicker">Your academic workspace</p><h2>Welcome, {displayName}</h2><p>Keep your records organised and your next task in view.</p></div><span className="live-welcome-symbol" aria-hidden="true"><PortalIcon name="brand" /></span></section>
          <section aria-labelledby="workspace-heading" className="live-workspaces"><div className="live-section-heading"><div><h2 id="workspace-heading">Your workspaces</h2><p>Available to your signed-in account.</p></div><span className="live-section-detail">{roleTitle}</span></div>
            <div className="live-tiles">{links.filter(([key]) => !['dashboard', 'account'].includes(key)).map(([key, label]) => <Link key={key} to={`/portal/${user.role}/${key}`}><span className="live-tile-icon"><PortalIcon name={key} /></span><strong>{label}</strong><p>{tileDescriptions[key]}</p><span className="live-tile-action">Open workspace <PortalIcon name="arrow" /></span></Link>)}</div></section>
          {isHod(user) && <section className="live-admin-note"><span className="live-tile-icon"><PortalIcon name="account" /></span><div><h2>Department administration</h2><p>Manage staff and part-adviser assignments in <Link to={`/portal/${user.role}/account`}>Account settings</Link>. Manage the catalogue, semester offerings and teaching assignments in <Link to="/portal/hod/courses">Courses</Link>.</p></div></section>}</div>}
        {['students', 'profile', 'results'].includes(section) && <Records key={`${user.id}:${section}`} section={section} user={user} />}
        {section === 'earlier-messages' && <Records key={`${user.id}:legacy-messages`} section="messages" user={user} />}
        {['messages', 'materials', 'timetable'].includes(section) && <Teaching key={`${user.id}:${section}`} section={section} user={user} />}
        {section === 'workflows' && <StudentRecordsBatch key={user.id} user={user} />}
        {section === 'attendance' && <Attendance key={user.id} user={user} />}
        {section === 'guardian-results' && <GuardianResults key={user.id} />}
        {section === 'academic-session' && <AcademicSession />}
        {section === 'courses' && <Courses user={user} />}
        {section === 'imports' && <RecordImports key={user.id} user={user} />}
        {section === 'account' && <AccountSettings user={user} />}
      </Suspense>}
      <footer className="live-footer"><span>OAU EEE · Department portal</span><span>Signed in as {user.username} · Private departmental records</span></footer></main></div>;
}
