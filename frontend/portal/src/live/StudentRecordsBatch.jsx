import { useEffect, useState } from 'react';
import { apiRequest, collectPages, getMyStudentProfile, listManagedStaff, listStudents } from '../api';
import { useAuth } from '../auth/useAuth';
import DocumentUpload from '../pages/DocumentUpload';
import { useRemote, formatDate, isHod } from './resources';
import { Alert, Empty, Pager, RemoteState, Table } from './ui';

const documentLabels = {
  clearance: 'Clearance certificate', jamb: 'JAMB result', waec: 'WAEC result',
  birth_cecrtificate: 'Birth certificate', state_origin: 'State of origin certificate',
  biodata: 'Student biodata form', result: 'Result', other: 'Other document',
};
const fieldLabels = {
  phone_number: 'Phone number', email: 'Email', full_name: 'Name', relationship: 'Relationship',
  address: 'Address', current_level: 'Level', programme: 'Programme', identifier_value: 'Matric number',
};

export default function StudentRecordsBatch({ user }) {
  const { refreshUser } = useAuth();
  const [studentId, setStudentId] = useState('');
  const [studentName, setStudentName] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const students = useRemote((signal) => user.is_staff
    ? listStudents({ search, page }, signal) : Promise.resolve(null), [user.id, user.is_staff, search, page]);
  const file = useRemote(async (signal) => {
    if (!studentId) return null;
    const [details, documents] = await Promise.all([
      apiRequest(`/api/workflows/students/${encodeURIComponent(studentId)}/`, { signal }),
      apiRequest(`/api/students/${encodeURIComponent(studentId)}/documents/`, { signal }),
    ]);
    return { ...details, documents };
  }, [user.id, studentId]);
  const handovers = useRemote((signal) => user.is_staff
    ? apiRequest('/api/workflows/handover/', { signal }) : Promise.resolve([]), [user.id, user.is_staff]);
  const staff = useRemote((signal) => isHod(user)
    ? collectPages((number, abort) => listManagedStaff({ page: number, is_active: 'true' }, abort), signal)
    : Promise.resolve([]), [user.id, user.is_superuser]);

  useEffect(() => {
    if (user.is_staff) return undefined;
    const controller = new AbortController();
    getMyStudentProfile(controller.signal).then((row) => {
      if (!controller.signal.aborted) {
        setStudentId(row.student_id);
        setStudentName(row.full_name);
      }
    }).catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [user.id, user.is_staff]);

  async function action(path, body, success) {
    if (busy) return false;
    setBusy(true); setError(''); setNotice('');
    try {
      await apiRequest(path, { method: 'POST', body });
      file.reload(); handovers.reload();
      setNotice(success);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally { setBusy(false); }
  }

  async function download(document) {
    setError('');
    try {
      const blob = await apiRequest(`/api/documents/${document.document_id}/download/`, { responseType: 'blob' });
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement('a');
      link.href = url; link.download = document.original_filename;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(err.message); }
  }

  function selectStudent(row) {
    setStudentId(row.student_id);
    setStudentName(row.full_name);
    setError(''); setNotice('');
  }

  return <div className="live-stack">
    <Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}
    {user.is_staff && <section className="live-card"><h2>Choose a student</h2>
      <form className="live-form" onSubmit={(event) => {
        event.preventDefault(); setSearch(new FormData(event.currentTarget).get('search').trim()); setPage(1);
      }}><label>Find by name or matric number<input name="search" type="search" /></label><button>Find students</button></form>
      <RemoteState resource={students}>{(data) => data?.results?.length ? <>
        <Table headings={['Student', 'Matric / registration number', 'File']}>
          {data.results.map((row) => <tr key={row.student_id}><td>{row.full_name}</td><td>{row.identifier_value}</td>
            <td><button disabled={busy} onClick={() => selectStudent(row)}>Open file for {row.full_name}</button></td></tr>)}
        </Table><Pager page={page} data={data} onChange={setPage} disabled={busy} />
      </> : <Empty>No students match your authorised scope and search.</Empty>}</RemoteState>
    </section>}

    {studentId && <RemoteState resource={file}>{(data) => data?.student_id === studentId && <>
      <section className="live-card"><h2>{studentName ? `${studentName}'s documents` : 'Student documents'}</h2>
        <button onClick={file.reload} disabled={busy}>Refresh file and requests</button>
        <DocumentUpload key={studentId} studentId={studentId} />
        <h3>Document versions</h3><p>The current document remains active while a student replacement awaits approval. Earlier approved versions remain available.</p>
        {!data.documents.length && <Empty>No documents have been uploaded.</Empty>}
        {data.documents.map((document) => <article className="live-inset" key={document.document_id}>
          <h4>{documentLabels[document.document_type] || document.document_type}</h4>
          <p>{document.original_filename} · {document.approval_state} · {formatDate(document.uploaded_at)}</p>
          {document.review_reason && <p>Review reason: {document.review_reason}</p>}
          <button onClick={() => download(document)}>Download {document.original_filename}</button>
          {data.can_review && document.approval_state === 'pending' && <ReviewForm busy={busy}
            onSubmit={(approve, reason) => action(`/api/documents/${document.document_id}/review/`, { approve, reason }, 'Replacement review saved.')} />}
        </article>)}
      </section>

      {!user.is_staff && <ChangeRequestForm key={studentId} data={data} busy={busy}
        onSubmit={(values) => action(`/api/workflows/students/${studentId}/`, { action: 'change_request', ...values }, 'Your request is awaiting part-adviser or HOD review.')} />}

      <section className="live-card"><h2>Correction requests</h2>
        {!data.requests.length && <Empty>No correction requests.</Empty>}
        {data.requests.map((row) => <article key={row.id} className="live-inset">
          <h3>{row.kind === 'identity' ? 'Identity or academic correction' : row.kind === 'guardian' ? 'Guardian change' : 'Contact change'} · {row.state}</h3>
          <dl>{Object.entries(row.values).filter(([name]) => name in fieldLabels).map(([name, value]) =>
            <div key={name}><dt>{fieldLabels[name]}</dt><dd>{String(value || 'Not supplied')}</dd></div>)}</dl>
          <p>Request reason: {row.reason}</p>{row.review_reason && <p>Review reason: {row.review_reason}</p>}
          {data.can_review && row.state === 'pending' && <ReviewForm busy={busy}
            onSubmit={(approve, reason) => action(`/api/workflows/requests/${row.id}/review/`, { approve, reason }, 'Correction request reviewed.')} />}
        </article>)}
      </section>

      {data.can_review && <section className="live-card"><h2>Source GPA comparison reviews</h2>
        {!data.source_comparisons.length && <Empty>No source comparisons for this student.</Empty>}
        {data.source_comparisons.map((comparison) => <article key={comparison.id} className="live-inset">
          <h3>{comparison.source.current_session} · {comparison.source.current_semester} · {comparison.review_status}</h3>
          <p>These values describe the saved import comparison. Current verified calculations remain available in Results.</p>
          <Table headings={['Measure', 'Calculated at import', 'Source reported', 'Difference']}>
            {['gpa', 'cgpa'].map((key) => <tr key={key}><td>{key.toUpperCase()}</td>
              <td><strong>{comparison.comparison_at_import[key]?.calculated ?? 'Not comparable'}</strong></td>
              <td>{comparison.comparison_at_import[key]?.reported ?? 'Not reported'}</td>
              <td>{comparison.comparison_at_import[key]?.difference ?? 'Not comparable'}</td></tr>)}
          </Table>
          {comparison.reviews.map((review, index) => <p key={index}>{review.reason} · {formatDate(review.created_at)} · HOD notification {review.notification_state === 'unknown' ? 'delivery unconfirmed' : review.notified_hod ? 'accepted by email service' : 'pending'}</p>)}
          <form className="live-form" onSubmit={(event) => {
            event.preventDefault(); action(`/api/workflows/source-comparisons/${comparison.id}/review/`,
              { reason: new FormData(event.currentTarget).get('reason') }, 'Review saved. The notification status is shown below.');
          }}><label>Discrepancy review reason<textarea name="reason" required maxLength={1000} /></label>
            <button disabled={busy}>Record review and notify HOD</button></form>
        </article>)}
      </section>}

      {isHod(user) && <section className="live-card"><h2>Archive student</h2>
        <p>The record and document history are retained; the student's login is deactivated.</p>
        <form className="live-form" onSubmit={(event) => {
          event.preventDefault();
          if (window.confirm('Archive this student and deactivate their login?')) action(`/api/workflows/students/${studentId}/`,
            { action: 'archive', reason: new FormData(event.currentTarget).get('reason') }, 'Student archived and login deactivated.');
        }}><label>Archive reason<textarea name="reason" required maxLength={1000} /></label><button disabled={busy}>Archive and deactivate</button></form>
      </section>}
    </>}</RemoteState>}

    {user.is_staff && <section className="live-card"><h2>HOD handover</h2>
      {isHod(user) && <RemoteState resource={staff}>{(rows) => <form className="live-form" onSubmit={(event) => {
        event.preventDefault(); action('/api/workflows/handover/',
          { target_id: Number(new FormData(event.currentTarget).get('target_id')) }, 'Handover offered. The incoming HOD must accept.');
      }}><label>Incoming HOD<select name="target_id" required defaultValue=""><option value="" disabled>Choose an active staff member</option>
        {rows.filter((row) => row.id !== user.id).map((row) => <option key={row.id} value={row.id}>{`${row.first_name || ''} ${row.last_name || ''}`.trim() || row.username}</option>)}
      </select></label><button disabled={busy}>Offer HOD handover</button></form>}</RemoteState>}
      <RemoteState resource={handovers}>{(rows) => rows.length ? rows.map((row) => <article key={row.id} className="live-inset">
        <p>Handover offered {formatDate(row.created_at)} · {row.state}</p>
        {row.recipient_id === user.id && row.state === 'pending' && <button disabled={busy} onClick={async () => {
          if (!window.confirm('Accept responsibility as Head of Department?')) return;
          if (await action('/api/workflows/handover/', { handover_id: row.id }, 'HOD responsibility accepted.')) await refreshUser();
        }}>Accept HOD responsibility</button>}
      </article>) : <Empty>No HOD handover offers.</Empty>}</RemoteState>
    </section>}
  </div>;
}

function ChangeRequestForm({ data, busy, onSubmit }) {
  const [kind, setKind] = useState('contact');
  const [guardianId, setGuardianId] = useState('');
  const [error, setError] = useState('');
  const guardian = data.guardians.find((row) => String(row.guardian_id) === guardianId);
  function submit(event) {
    event.preventDefault(); setError('');
    const form = new FormData(event.currentTarget);
    const names = kind === 'contact' ? ['phone_number', 'email'] : kind === 'guardian'
      ? ['full_name', 'phone_number', 'relationship', 'email', 'address']
      : ['full_name', 'current_level', 'programme', 'identifier_value'];
    const values = Object.fromEntries(names.map((name) => [name, String(form.get(name) || '').trim()])
      .filter(([, value]) => kind !== 'identity' || value));
    if (kind === 'guardian' && guardianId) values.guardian_id = guardianId;
    if (values.current_level) values.current_level = Number(values.current_level);
    if (!Object.keys(values).length) { setError('Enter at least one correction.'); return; }
    onSubmit({ kind, values, reason: form.get('reason') });
  }
  return <section className="live-card"><h2>Request a correction</h2>
    <p>Your current details stay active until the part adviser or HOD approves your request.</p>
    <label>Details to change<select value={kind} onChange={(event) => { setKind(event.target.value); setError(''); }}>
      <option value="contact">My contact details</option><option value="guardian">Parent, guardian or sponsor</option>
      <option value="identity">Name, matric number or academic details</option></select></label>
    {kind === 'guardian' && <label>Guardian<select value={guardianId} onChange={(event) => setGuardianId(event.target.value)}>
      <option value="">Add a new parent, guardian or sponsor</option>{data.guardians.map((row) => <option key={row.guardian_id} value={row.guardian_id}>{row.full_name} · {row.relationship}</option>)}
    </select></label>}
    <form className="live-form" key={`${kind}:${guardianId}`} onSubmit={submit}>
      {kind === 'contact' && <><label>Phone number<input name="phone_number" defaultValue={data.phone_number || ''} maxLength={30} /></label>
        <label>Email<input name="email" type="email" defaultValue={data.email || ''} /></label></>}
      {kind === 'guardian' && <><label>Full name<input name="full_name" required maxLength={200} defaultValue={guardian?.full_name || ''} /></label>
        <label>Relationship<input name="relationship" required maxLength={100} defaultValue={guardian?.relationship || ''} /></label>
        <label>Phone number<input name="phone_number" required maxLength={30} defaultValue={guardian?.phone_number || ''} /></label>
        <label>Email<input name="email" type="email" defaultValue={guardian?.email || ''} /></label>
        <label>Address<textarea name="address" defaultValue={guardian?.address || ''} /></label></>}
      {kind === 'identity' && <><p>Fill only the fields that need correcting. Authorised staff review identity and academic changes.</p>
        <label>Correct name<input name="full_name" maxLength={200} /></label><label>Correct matric number<input name="identifier_value" maxLength={100} /></label>
        <label>Correct level<input name="current_level" type="number" min="100" max="900" step="100" /></label><label>Correct programme<input name="programme" maxLength={150} /></label></>}
      <label>Reason for the change<textarea name="reason" required maxLength={1000} /></label>
      <Alert>{error}</Alert><button disabled={busy}>Submit for approval</button>
    </form>
  </section>;
}

function ReviewForm({ busy, onSubmit }) {
  return <form className="live-form" onSubmit={(event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    onSubmit(form.get('decision') === 'approve', form.get('reason'));
  }}><label>Decision<select name="decision"><option value="approve">Approve</option><option value="reject">Reject</option></select></label>
    <label>Review reason<textarea name="reason" required maxLength={1000} /></label><button disabled={busy}>Save review</button></form>;
}
