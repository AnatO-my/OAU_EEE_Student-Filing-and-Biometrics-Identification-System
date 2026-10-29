import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../api';
import { Alert, Empty, RemoteState, Table } from './ui';
import { formatDate, hasPermission, useRemote } from './resources';

const endpoint = '/api/teaching/';
const courseName = (rows, id) => rows?.find(row => row.id === id)?.course || 'Course';
function attempt(ref, payload) {
  const key = JSON.stringify(payload);
  if (ref.current?.key !== key) ref.current = { key, id: crypto.randomUUID() };
  return { ...payload, event_id: ref.current.id };
}
function CourseSelect({ courses, name = 'offering', defaultValue = '', disabled = false }) {
  return <label>Course<select name={name} defaultValue={defaultValue} required disabled={disabled}><option value="">Choose a course</option>{courses.map(row => <option key={row.id} value={row.id}>{row.course} · {row.session} · {row.semester}</option>)}</select></label>;
}

function MessageWorkspace({ user }) {
  const list = useRemote(signal => apiRequest(`${endpoint}messages/`, { signal }), []);
  const courses = useRemote(signal => apiRequest(`${endpoint}courses/`, { signal }), []);
  const [selected, setSelected] = useState(null), [editing, setEditing] = useState(null), [history, setHistory] = useState(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  const key = useRef(null), readerHeading = useRef(null), inboxHeading = useRef(null);
  const [opening, setOpening] = useState(false);
  useEffect(() => {
    if (selected) { readerHeading.current?.focus(); readerHeading.current?.scrollIntoView?.({ block: 'start' }); }
  }, [selected]);
  const canPublish = hasPermission(user, 'teaching.publish_message');
  const directory = useRemote(signal => canPublish ? apiRequest(`${endpoint}audience-options/`, { signal }) : Promise.resolve({ students: [], staff: [] }), [canPublish]);
  const requestedId = new URLSearchParams(window.location.search).get('message');
  const recipientName = id => directory.data?.staff.find(row => row.id === id)?.full_name || directory.data?.students.find(row => row.user_id === id)?.full_name || 'Selected recipient';
  async function open(id) {
    setBusy(true); setOpening(true); setSelected(null); setEditing(null); setHistory(null); setError(''); setNotice('');
    try { const row = await apiRequest(`${endpoint}messages/${id}/`); setSelected(row); setEditing(null); setHistory(null); list.reload(); }
    catch (err) { setError(err.message); } finally { setBusy(false); setOpening(false); }
  }
  function refreshMessages() {
    setSelected(null); setEditing(null); setHistory(null); setNotice('');
    list.reload(); courses.reload(); directory.reload();
  }
  function closeMessage() {
    setSelected(null); setEditing(null); setHistory(null); inboxHeading.current?.focus();
  }
  async function save(event) {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form);
    const audience = { students: data.get('students') === 'on', staff: data.get('staff') === 'on' };
    if (data.get('level')) audience.level = Number(data.get('level'));
    if (data.get('offering')) audience.offering_ids = [Number(data.get('offering'))];
    if (data.getAll('student_ids').length) audience.student_ids = data.getAll('student_ids');
    if (data.getAll('staff_ids').length) audience.staff_ids = data.getAll('staff_ids').map(Number);
    const payload = attempt(key, { subject: data.get('subject'), body: data.get('body'), audience, expected_version: editing?.version || 0 });
    setBusy(true); setError(''); setNotice('');
    try { const row = await apiRequest(`${endpoint}messages/${editing ? `${editing.id}/` : ''}`, { method: editing ? 'PUT' : 'POST', body: payload }); setSelected(row); setEditing(null); key.current = null; form.reset(); list.reload(); setNotice('Published on the website. Link notifications are queued for the mail worker.'); }
    catch (err) { setError(`${err.message} Check the message list before retrying an uncertain publication.`); } finally { setBusy(false); }
  }
  async function withdraw(event) {
    event.preventDefault(); const payload = attempt(key, { subject: selected.subject, body: '', audience: selected.audience, expected_version: selected.version, withdrawn: true }); setBusy(true); setError('');
    try { const row = await apiRequest(`${endpoint}messages/${selected.id}/`, { method: 'PUT', body: payload }); setSelected(row); key.current = null; list.reload(); setNotice('Message withdrawn. A short withdrawal notification is queued.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function showHistory() {
    try { setHistory(await apiRequest(`${endpoint}messages/${selected.id}/history/`)); } catch (err) { setError(err.message); }
  }
  return <><section className="live-card"><h2 ref={inboxHeading} tabIndex={-1}>Department messages</h2><p>Email notifications contain a sign-in link. A message is marked read only when its recipient opens it here.</p><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}{requestedId && <p>The linked message is highlighted below. Choose Open message to read it.</p>}<button disabled={busy} onClick={refreshMessages}>Refresh messages</button>{opening && <p role="status">Opening message...</p>}
    <RemoteState resource={list}>{rows => !rows.length ? <Empty>No current messages are available.</Empty> : <Table headings={['Subject', 'Version', 'Status', 'Open']}>
      {rows.map(row => <tr key={row.id} aria-current={row.id === requestedId ? 'true' : undefined} style={row.id === requestedId ? { background: 'rgba(59,130,246,.12)' } : undefined}><td>{row.subject}{row.id === requestedId && ' · Linked message'}</td><td>{row.version}</td><td>{row.withdrawn ? 'Withdrawn' : row.is_sender ? `${row.read_count}/${row.recipient_count} recipients read` : row.read_at ? 'Read' : 'Unread'}</td><td><button disabled={busy} onClick={() => open(row.id)}>Open message</button></td></tr>)}</Table>}</RemoteState>
    {selected && <article className="live-inset" aria-labelledby="teaching-message-heading"><h3 id="teaching-message-heading" ref={readerHeading} tabIndex={-1}>{selected.subject} · Version {selected.version}</h3><button disabled={busy} onClick={closeMessage}>Close message</button>{selected.withdrawn ? <p>This message has been withdrawn.</p> : <p style={{ whiteSpace: 'pre-wrap' }}>{selected.body}</p>}<p>Published: {formatDate(selected.created_at)}</p>{!selected.is_sender && <p>{selected.read_at ? `Read on website: ${formatDate(selected.read_at)}` : 'Opened message'}</p>}
      {selected.is_sender && <><button disabled={busy} onClick={showHistory}>Review versions and recipient reads</button>{!selected.withdrawn && <><button onClick={() => setEditing(selected)}>Edit as a new version</button><form onSubmit={withdraw}><label><input type="checkbox" required /> Confirm withdrawal; retain version history</label><button disabled={busy}>Withdraw message</button></form></>}</>}
      {history && <div>{history.map(version => <section key={version.version}><h4>Version {version.version} · {version.withdrawn ? 'Withdrawn' : 'Published'}</h4><p className="live-message">{version.withdrawn ? 'This version withdrew the message.' : version.body}</p><p>{version.read_count}/{version.recipient_count} recipients read</p><Table headings={['Recipient account', 'Read on website']} >{version.receipts.map(receipt => <tr key={receipt.recipient_id}><td>{recipientName(receipt.recipient_id)}</td><td>{formatDate(receipt.read_at)}</td></tr>)}</Table></section>)}</div>}
    </article>}
  </section>{canPublish && <section className="live-card"><h2>{editing ? `Edit message version ${editing.version}` : 'Publish a message'}</h2><p>Publish directly to student or staff audiences. Course and level filters apply to the selected audience. No approval step is required.</p><RemoteState resource={courses}>{rows => <form key={editing ? `${editing.id}:${editing.version}` : 'new'} className="live-form" onSubmit={save}>
    <label>Subject<input name="subject" maxLength={200} required defaultValue={editing?.subject || ''} disabled={busy} /></label><label>Message<textarea name="body" maxLength={20000} required defaultValue={editing?.body || ''} disabled={busy} /></label>
    <label><input type="checkbox" name="students" defaultChecked={editing?.audience?.students ?? true} /> Students</label><label><input type="checkbox" name="staff" defaultChecked={editing?.audience?.staff || false} /> Staff</label>
    <label>Level filter (optional)<input name="level" type="number" min="1" defaultValue={editing?.audience?.level || ''} /></label>
    <label>Course filter (optional)<select name="offering" defaultValue={editing?.audience?.offering_ids?.[0] || ''}><option value="">All selected recipients</option>{rows.map(row => <option key={row.id} value={row.id}>{row.course} · {row.session}</option>)}</select></label>
    <RemoteState resource={directory}>{people => <><label>Specific students (optional; select several with Ctrl or Command)<select multiple name="student_ids" defaultValue={editing?.audience?.student_ids || []}>{people.students.map(person => <option key={person.id} value={person.id}>{person.full_name} · {person.identifier_value}</option>)}</select></label><label>Specific staff (optional)<select multiple name="staff_ids" defaultValue={editing?.audience?.staff_ids?.map(String) || []}>{people.staff.map(person => <option key={person.id} value={person.id}>{person.full_name}</option>)}</select></label></>}</RemoteState>
    <button className="live-primary" disabled={busy}>{editing ? 'Publish revised version and reset unread state' : 'Publish and queue link notifications'}</button>{editing && <button type="button" onClick={() => setEditing(null)}>Cancel edit</button>}
  </form>}</RemoteState></section>}</>;
}

function MaterialWorkspace({ user }) {
  const list = useRemote(signal => apiRequest(`${endpoint}materials/`, { signal }), []);
  const courses = useRemote(signal => apiRequest(`${endpoint}courses/`, { signal }), []);
  const [editing, setEditing] = useState(null), [history, setHistory] = useState(null), [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  const key = useRef(null), canManage = hasPermission(user, 'teaching.manage_material');
  async function save(event, withdrawn = false, item = editing) {
    event.preventDefault(); if (busy) return; const form = event.currentTarget; const data = new FormData(form);
    if (!key.current) key.current = crypto.randomUUID();
    data.set('event_id', key.current); data.set('expected_version', item?.version || 0); data.set('withdrawn', String(withdrawn));
    if (item) { data.set('offering', item.offering); data.set('title', item.title); }
    setBusy(true); setError(''); setNotice('');
    try { await apiRequest(`${endpoint}materials/${item ? `${item.id}/` : ''}`, { method: item ? 'PUT' : 'POST', rawBody: data }); key.current = null; form.reset(); setEditing(null); setHistory(null); setNotice(withdrawn ? 'Material withdrawn successfully.' : item ? 'Material replacement saved successfully.' : 'Material uploaded successfully.'); list.reload(); }
    catch (err) { setError(`${err.message} Refresh material versions before retrying an uncertain upload.`); } finally { setBusy(false); }
  }
  async function download(row) {
    try { const blob = await apiRequest(row.download_url, { responseType: 'blob' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = row.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); } catch (err) { setError(err.message); }
  }
  async function versions(row) { try { setHistory(await apiRequest(`${endpoint}materials/${row.id}/`)); } catch (err) { setError(err.message); } }
  return <section className="live-card"><h2>Course materials</h2><p>Downloads require current course-roster membership. Replaced files remain in the assigned staff archive.</p><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}<button disabled={busy} onClick={() => { list.reload(); courses.reload(); }}>Refresh materials</button><RemoteState resource={list}>{rows => !rows.length ? <Empty>No course materials are available.</Empty> : <Table headings={['Title', 'Course', 'Version', 'Action']}>
    {rows.map(row => <tr key={row.id}><td>{row.title}{row.withdrawn && ' · Withdrawn'}</td><td>{courseName(courses.data, row.offering)}</td><td>{row.version}</td><td>{!row.withdrawn && <button onClick={() => download(row)}>Download</button>}{canManage && <><button disabled={busy} onClick={() => { setEditing(row); key.current = null; setNotice(''); }}>Replace</button><button onClick={() => versions(row)}>Version archive</button><form onSubmit={event => save(event, true, row)}><input name="reason" placeholder="Written withdrawal reason" required maxLength={1000} /><label><input type="checkbox" required /> Confirm withdrawal</label><button disabled={busy}>Withdraw</button></form></>}</td></tr>)}</Table>}</RemoteState>
    {history && <><h3>Retained versions</h3>{history.map(row => <p key={row.version}>Version {row.version} · {row.withdrawn ? 'Withdrawn' : row.filename} {!row.withdrawn && <button onClick={() => download(row)}>Download archived version</button>}</p>)}</>}
    {canManage && <RemoteState resource={courses}>{rows => <form key={editing?.id || 'new'} className="live-form" onSubmit={save}><h3>{editing ? `Replace ${editing.title}` : 'Upload a material'}</h3>{!editing && !rows.length && <p>No course offerings are available. Ask the HOD to create an offering and assign you to it. Staff also need the course-material permission. Then refresh materials.</p>}{!editing && <><CourseSelect courses={rows} /><label>Title<input name="title" maxLength={200} required /></label></>}<label>Material file<input name="upload" type="file" accept=".pdf,.txt,.csv,.docx,.pptx,.xlsx" required disabled={busy} /></label><p>PDF, text, CSV or Office files; maximum 20 MiB.</p><label>Written reason<input name="reason" maxLength={1000} required /></label><button disabled={busy || (!editing && !rows.length)}>Save material version</button>{editing && <button disabled={busy} type="button" onClick={() => { setEditing(null); key.current = null; }}>Cancel replacement</button>}</form>}</RemoteState>}
  </section>;
}

function TimetableWorkspace({ user }) {
  const list = useRemote(signal => apiRequest(`${endpoint}timetable/`, { signal }), []), courses = useRemote(signal => apiRequest(`${endpoint}courses/`, { signal }), []);
  const [editing, setEditing] = useState(null), [notice, setNotice] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const key = useRef(null), canManage = hasPermission(user, 'teaching.manage_timetable');
  async function save(event) {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget));
    const payload = attempt(key, { offering: Number(editing?.offering || data.offering), title: data.title, venue: data.venue,
      starts_at: new Date(data.starts_at).toISOString(), ends_at: new Date(data.ends_at).toISOString(), active: data.active === 'on', reason: data.reason, expected_revision: editing?.revision || 0 });
    setBusy(true); setError(''); setNotice('');
    try { const result = await apiRequest(`${endpoint}timetable/${editing ? `${editing.id}/` : ''}`, { method: editing ? 'PUT' : 'POST', body: payload }); key.current = null; setEditing(null); list.reload(); setNotice(result.warning || 'Timetable saved. No overlapping approved student rosters were found.'); }
    catch (err) { setError(`${err.message} Check saved entries before retrying an uncertain change.`); } finally { setBusy(false); }
  }
  const localDate = value => { if (!value) return ''; const date = new Date(value); return new Date(date.getTime() - date.getTimezoneOffset()*60000).toISOString().slice(0,16); };
  return <section className="live-card"><h2>Course timetable</h2><p>Course staff maintain their own entries. Overlapping approved student rosters produce warnings and do not block saving.</p><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}<button onClick={list.reload}>Refresh timetable</button><RemoteState resource={list}>{rows => !rows.length ? <Empty>No timetable entries are available.</Empty> : <Table headings={['Course', 'Activity', 'Time', 'Venue', 'Clashes', ...(canManage ? ['Edit'] : [])]}>{rows.map(row => <tr key={row.id}><td>{courseName(courses.data, row.offering)}</td><td>{row.title}{!row.active && ' · Withdrawn'}</td><td>{formatDate(row.starts_at)} – {formatDate(row.ends_at)}</td><td>{row.venue}</td><td>{row.warning || 'None'}</td>{canManage && <td><button onClick={() => setEditing(row)}>Edit entry</button></td>}</tr>)}</Table>}</RemoteState>
    {canManage && <RemoteState resource={courses}>{rows => <form key={editing ? `${editing.id}:${editing.revision}` : 'new'} className="live-form" onSubmit={save}><h3>{editing ? 'Edit timetable entry' : 'Add timetable entry'}</h3>{!editing && <CourseSelect courses={rows} />}<label>Activity<input name="title" required maxLength={200} defaultValue={editing?.title || ''} /></label><label>Venue<input name="venue" required maxLength={200} defaultValue={editing?.venue || ''} /></label><label>Starts (local time)<input name="starts_at" type="datetime-local" required defaultValue={localDate(editing?.starts_at)} /></label><label>Ends (local time)<input name="ends_at" type="datetime-local" required defaultValue={localDate(editing?.ends_at)} /></label><label><input type="checkbox" name="active" defaultChecked={editing?.active ?? true} /> Entry active</label><label>Written reason<input name="reason" required maxLength={1000} /></label><button disabled={busy}>Save timetable and show overlaps</button>{editing && <button type="button" onClick={() => setEditing(null)}>Cancel edit</button>}</form>}</RemoteState>}
  </section>;
}

export default function Teaching({ user, section = 'messages' }) {
  return section === 'materials' ? <MaterialWorkspace user={user} /> : section === 'timetable' ? <TimetableWorkspace user={user} /> : <MessageWorkspace user={user} />;
}
