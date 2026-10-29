import { useState } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api';
import { Alert, Empty, RemoteState, Table } from './ui';
import { isHod, useRemote } from './resources';

const staffLabel = row => `${[row.first_name, row.last_name].filter(Boolean).join(' ') || row.username} (${row.username})`;
const courseLabel = (data, id) => data.courses.find(row => row.id === id)?.code || `Course ${id}`;
const sessionLabel = (data, id) => data.sessions.find(row => row.id === id)?.name || `Session ${id}`;
const offeringLabel = (data, row) => `${courseLabel(data, row.course)} · ${sessionLabel(data, row.academic_session)} · ${row.semester}`;
const outcomeMessage = error => error.status === 0 || error.status >= 500
  ? `${error.message} The save outcome is uncertain. Refresh and check the saved records before submitting again.` : error.message;

export default function Courses({ user }) {
  // Do not even request private HOD lists when this component is used directly by another role.
  return isHod(user) ? <CourseManagement /> : <section className="live-card"><h2>HOD access required</h2><p>Only the HOD can manage courses and teaching assignments.</p></section>;
}

function CourseManagement() {
  const resource = useRemote(async signal => {
    const [courses, offerings, sessions, scales, staff] = await Promise.all([
      api.collectPages(api.listCourses, signal), api.collectPages(api.listCourseOfferings, signal),
      api.collectPages(api.listAcademicSessions, signal), api.collectPages(api.listGradingScales, signal),
      api.collectPages((page, pageSignal) => api.listManagedStaff({ page }, pageSignal), signal),
    ]);
    return { courses, offerings, sessions, scales: scales.filter(row => row.is_published), staff };
  }, []);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  async function save(event, operation, message) {
    event.preventDefault();
    const form = event.currentTarget, values = new FormData(form);
    setBusy(true); setError(''); setNotice('');
    try { await operation(values); form.reset(); setNotice(message); resource.reload(); }
    catch (err) { setError(outcomeMessage(err)); }
    finally { setBusy(false); }
  }
  return <><section className="live-card"><h2>Course management</h2><p>Create a course once, then add an offering for each session and semester. Teaching assignments apply to a specific offering. Confirm student rosters separately in <Link to="/portal/hod/attendance">Attendance</Link>.</p><button disabled={busy} onClick={resource.reload}>Refresh course records</button><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}</section>
    <RemoteState resource={resource}>{data => <>
      <section className="live-card"><h2>Course catalogue</h2>{data.courses.length ? <Table headings={['Code', 'Title']}>{data.courses.map(row => <tr key={row.id}><td>{row.code}</td><td>{row.title}</td></tr>)}</Table> : <Empty>No courses have been created.</Empty>}
        <form className="live-form" onSubmit={event => save(event, values => api.createCourse(values.get('code').trim(), values.get('title').trim()), 'Course created. You can now add its semester offering.')}><h3>Create a course</h3><label>Course code<input name="code" maxLength={30} required disabled={busy} /></label><label>Course title<input name="title" maxLength={200} required disabled={busy} /></label><button disabled={busy}>Create course</button></form>
      </section>
      <section className="live-card"><h2>Academic sessions</h2><p>Creating a session does not change the current academic period. Select that separately in <Link to="/portal/hod/academic-session">Academic session</Link>.</p>
        {data.sessions.length ? <p>Recorded sessions: {data.sessions.map(row => row.name).join(', ')}</p> : <Empty>No academic sessions have been created.</Empty>}
        <form className="live-form" onSubmit={event => save(event, values => api.createAcademicSession(values.get('name').trim()), 'Academic session created; the current session was not changed.')}><label>New academic session<input name="name" placeholder="2026/2027" pattern="[0-9]{4}/[0-9]{4}" maxLength={9} required disabled={busy} /></label><button disabled={busy}>Create academic session</button></form>
      </section>
      <section className="live-card"><h2>Semester offerings</h2>{data.offerings.length ? <Table headings={['Course', 'Session', 'Semester', 'Level', 'Units', 'Grading scale']}>{data.offerings.map(row => <tr key={row.id}><td>{courseLabel(data, row.course)}</td><td>{sessionLabel(data, row.academic_session)}</td><td>{row.semester}</td><td>{row.level}</td><td>{row.credit_units}</td><td>{data.scales.find(scale => scale.id === row.grading_scale)?.name || `Scale ${row.grading_scale}`}</td></tr>)}</Table> : <Empty>No semester offerings have been created.</Empty>}
        <form className="live-form" onSubmit={event => save(event, values => api.createCourseOffering({ course: Number(values.get('course')), academic_session: Number(values.get('academic_session')), semester: values.get('semester'), level: Number(values.get('level')), credit_units: Number(values.get('credit_units')), grading_scale: Number(values.get('grading_scale')) }), 'Semester offering created. Assign its teaching staff below.')}><h3>Add a semester offering</h3>
          <label>Catalogue course<select name="course" required disabled={busy}><option value="">Choose a course</option>{data.courses.map(row => <option key={row.id} value={row.id}>{row.code} · {row.title}</option>)}</select></label>
          <label>Offering academic session<select name="academic_session" required disabled={busy}><option value="">Choose a session</option>{data.sessions.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
          <label>Semester<select name="semester" required disabled={busy}><option value="">Choose a semester</option><option value="harmattan">Harmattan</option><option value="rain">Rain</option></select></label>
          <label>Level<input name="level" type="number" min={1} max={32767} step={1} required disabled={busy} /></label><label>Credit units<input name="credit_units" type="number" min={1} max={32767} step={1} required disabled={busy} /></label>
          <label>Published grading scale<select name="grading_scale" required disabled={busy}><option value="">Choose a grading scale</option>{data.scales.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
          {!data.scales.length && <p>No published grading scale is available. Complete the department grading setup before adding offerings.</p>}
          <button disabled={busy || !data.courses.length || !data.sessions.length || !data.scales.length}>Create semester offering</button>
        </form>
      </section>
      <TeachingAssignments data={data} />
    </>}</RemoteState></>;
}

function TeachingAssignments({ data }) {
  const [offering, setOffering] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const resource = useRemote(signal => offering ? api.collectPages((page, pageSignal) => api.apiRequest(`/api/attendance/offerings/${offering}/staff/`, { query: { page }, signal: pageSignal }), signal) : Promise.resolve([]), [offering]);
  async function save(event, staff, active) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try { await api.apiRequest(`/api/attendance/offerings/${offering}/staff/`, { method: 'PUT', body: { staff: Number(staff), is_active: active } }); resource.reload(); setNotice(active ? 'Teaching assignment activated.' : 'Teaching assignment deactivated.'); }
    catch (err) { setError(outcomeMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="live-card"><h2>Teaching staff assignments</h2><p>Assignment grants course scope, while the staff member still needs the relevant attendance or teaching permissions. Manage those permissions in <Link to="/portal/hod/account">Account settings</Link>. Staff access also follows the current academic session.</p>
    <label>Offering to manage<select value={offering} disabled={busy} onChange={event => { setOffering(event.target.value); setError(''); setNotice(''); }}><option value="">Choose an offering</option>{data.offerings.map(row => <option key={row.id} value={row.id}>{offeringLabel(data, row)}</option>)}</select></label>
    <Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}
    {offering && <><button disabled={busy} onClick={resource.reload}>Refresh teaching assignments</button><RemoteState resource={resource}>{rows => <>
      {rows.length ? <Table headings={['Staff', 'Assignment', 'Action']}>{rows.map(row => <tr key={row.id}><td>{row.staff_name || row.staff_username} ({row.staff_username}){!row.staff_is_active && ' · Account inactive'}</td><td>{row.is_active ? 'Active' : 'Inactive'}</td><td><form onSubmit={event => save(event, row.staff, !row.is_active)}><label><input type="checkbox" required disabled={busy || (!row.is_active && !row.staff_is_active)} /> Confirm assignment change</label><button disabled={busy || (!row.is_active && !row.staff_is_active)}>{row.is_active ? 'Deactivate assignment' : 'Reactivate assignment'}</button></form></td></tr>)}</Table> : <Empty>No teaching staff are assigned to this offering.</Empty>}
      <form className="live-form" key={offering} onSubmit={event => save(event, new FormData(event.currentTarget).get('staff'), true)}><label>Teaching staff<select name="staff" required disabled={busy}><option value="">Choose active staff</option>{data.staff.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{staffLabel(row)}</option>)}</select></label><label><input type="checkbox" required disabled={busy} /> Confirm this staff member should teach this offering</label><button disabled={busy || !data.staff.some(row => row.is_active)}>Assign teaching staff</button></form>
    </>}</RemoteState></>}
  </section>;
}
