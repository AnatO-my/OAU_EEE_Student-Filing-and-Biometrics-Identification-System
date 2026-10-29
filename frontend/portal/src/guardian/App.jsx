import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createApi } from './api.js';
import { useRemote } from '../useRemote';

const reasons = {
  results_missing_or_unverified: 'Results are missing or still awaiting verification.',
  no_guardians: 'No guardian has been added for this student.',
  sharing_not_enabled: 'Email sharing permission has not been recorded.',
  invalid_email: 'A valid guardian email address is required.',
  duplicate_contact: 'Duplicate contact; only one copy will be queued.',
  reviewed_data_changed: 'Results, contact details or sharing permission changed after review.',
  provider_not_configured: 'The sending account is not ready. Contact the administrator.',
  provider_rejected: 'The provider rejected the submission.',
  submission_uncertain: 'The submission outcome is uncertain. Check before sending anything again.',
};
const statuses = { draft: 'Ready for review', queued: 'Queued', processing: 'Sending',
  accepted: 'Accepted by provider', failed: 'Failed', unknown: 'Outcome uncertain',
  skipped: 'Skipped', cancelled: 'Cancelled' };
const reason = (code) => reasons[code] || code?.replaceAll('_', ' ') || '';
const isHod = (user) => user?.role === 'hod' && user.is_staff && user.is_superuser;
const running = (batch) => !!(batch?.counts?.queued || batch?.counts?.processing);

function Alert({ children }) { return children ? <div className="alert" role="alert">{children}</div> : null; }
function Empty({ children }) { return <p className="empty">{children}</p>; }
function Pager({ page, next, onChange, disabled }) {
  return <div className="pager"><button disabled={disabled || page === 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page}</span><button disabled={disabled || !next} onClick={() => onChange(page + 1)}>Next</button></div>;
}

export default function App({ api: suppliedApi }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const api = useMemo(() => suppliedApi || createApi({ onSessionLost() {
    setUser(null); setError('Your session ended or access changed. Sign in again.');
  } }), [suppliedApi]);

  useEffect(() => {
    let alive = true;
    api.me().then((value) => { if (alive) setUser(value); }).catch((err) => {
      if (alive) setError([401, 403].includes(err.status) ? '' : err.message);
    }).finally(() => { if (alive) setChecking(false); });
    return () => { alive = false; };
  }, [api]);

  async function login(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const username = data.get('username'), password = data.get('password');
    form.reset(); setBusy(true); setError('');
    try { setUser(await api.login(username, password)); } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError('');
    try { await api.logout(); setUser(null); } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <div className="shell"><header className="masthead"><a className="brand" href="./"><span className="mark">EEE</span>
    <span>Obafemi Awolowo University<small>Electrical &amp; Electronic Engineering</small></span></a>
    {user && <div className="identity"><span>{user.first_name || user.username}</span><button onClick={logout} disabled={busy}>Sign out</button></div>}</header>
    <main><div className="page-title"><p className="eyebrow">Department correspondence</p><h1>Guardian results</h1>
      <p>Reviewed results, sent privately to each student’s guardians.</p></div>
      <Alert>{error}</Alert>
      {checking ? <Empty>Checking your session…</Empty> : !user ? <section className="card login"><p className="eyebrow">HOD workspace</p><h2>Sign in to continue</h2>
        <p>Use your departmental account. The sending Gmail account is configured separately.</p>
        <form onSubmit={login}><label>Username<input name="username" autoComplete="username" required disabled={busy} /></label>
          <label>Password<input name="password" type="password" autoComplete="current-password" required disabled={busy} /></label>
          <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button></form></section> :
        !isHod(user) ? <section className="card"><h2>HOD access required</h2><p>This account cannot share guardian result reports. Sign out to use an authorized HOD account.</p></section> :
          <Workspace key={user.id} api={api} />}
    </main><footer>OAU EEE <span>Private academic correspondence</span></footer></div>;
}

export function Workspace({ api }) {
  const [panel, setPanel] = useState('new');
  const [reloadCatalog, setReloadCatalog] = useState(0);
  const [selectedSession, setSession] = useState('');
  const [semester, setSemester] = useState('harmattan');
  const [isRevised, setIsRevised] = useState(false), [revisionReason, setRevisionReason] = useState('');
  const [selected, setSelected] = useState({});
  const [batch, setBatch] = useState(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const attempt = useRef(null);

  const loadSessions = useCallback(() => api.sessions(), [api]);
  const catalog = useRemote(loadSessions, reloadCatalog);
  const sessions = catalog.data || [];
  const session = selectedSession || String(sessions.at(-1)?.id || '');
  const catalogLoading = catalog.loading;
  const catalogError = catalog.error?.message || '';

  function invalidate() { setBatch(null); setReviewed(false); setError(''); setNotice(''); attempt.current = null; }
  function toggleStudent(student) {
    invalidate();
    setSelected((old) => {
      const next = { ...old };
      if (next[student.student_id]) delete next[student.student_id];
      else if (Object.keys(next).length < 100) next[student.student_id] = student;
      return next;
    });
  }
  async function preview() {
    setBusy(true); setError(''); setNotice('');
    const payload = { student_ids: Object.keys(selected).sort(), academic_session: Number(session), semester, channels: ['email'], is_revised: isRevised, revision_reason: revisionReason };
    const signature = JSON.stringify(payload);
    if (attempt.current?.signature !== signature) attempt.current = { signature, id: crypto.randomUUID() };
    try {
      const value = await api.preview({ ...payload, request_id: attempt.current.id });
      setBatch(value); setReviewed(false); setPanel('review');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function refresh(id = batch?.id) {
    if (!id) return;
    setBusy(true); setError('');
    try { setBatch(await api.batch(id)); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function loadHistory(id) { setPanel('review'); setBatch(null); setReviewed(false); setNotice(''); await refresh(id); }
  async function send() {
    if (!reviewed || !batch || batch.queued_at) return;
    setBusy(true); setError('');
    try {
      const value = await api.send(batch); setBatch(value);
      setNotice('The batch is queued. You can follow each email below.');
    } catch (err) {
      setError(`${err.message} Refresh this batch’s status before trying again. Keep this batch rather than creating another send.`);
    } finally { setBusy(false); }
  }
  async function retry() {
    setBusy(true); setError('');
    try { const value = await api.retry(batch.id); setBatch(await api.batch(batch.id)); setNotice(`${value.requeued} failed submissions requeued.`); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const batchId = batch?.id;
  const isRunning = running(batch);
  useEffect(() => {
    if (!isRunning) return;
    let alive = true, inFlight = false;
    const id = batchId;
    const timer = setInterval(async () => {
      if (inFlight || document.visibilityState === 'hidden') return;
      inFlight = true;
      try { const value = await api.batch(id); if (alive) setBatch(value); }
      catch (err) { if (alive) setError(`Status refresh failed: ${err.message}`); }
      finally { inFlight = false; }
    }, 5000);
    return () => { alive = false; clearInterval(timer); };
  }, [api, batchId, isRunning]);

  const students = Object.values(selected);
  return <><nav className="tabs" aria-label="Result sharing"><button disabled={busy} aria-current={panel === 'new' ? 'page' : undefined} onClick={() => setPanel('new')}>1 · Choose students</button>
    <button disabled={busy || !batch} aria-current={panel === 'review' ? 'page' : undefined} onClick={() => setPanel('review')}>2 · Review &amp; send</button>
    <button disabled={busy} aria-current={panel === 'history' ? 'page' : undefined} onClick={() => setPanel('history')}>Batch history</button></nav>
    <Alert>{error}</Alert>{notice && <p className="notice" role="status">{notice}</p>}
    {panel === 'new' && <><section className="card"><div className="section-heading"><div><p className="eyebrow">01 / The right records</p><h2>Choose students and period</h2></div><span className="badge">Email</span></div>
      <p>Choose up to 100 students per batch. Each eligible guardian receives a separate report.</p>
      <Alert>{catalogError}</Alert>{catalogError && <button onClick={() => setReloadCatalog((n) => n + 1)}>Retry academic sessions</button>}
      <div className="fields"><label>Academic session<select value={session} disabled={busy || catalogLoading} onChange={(e) => { invalidate(); setSession(e.target.value); }}>
        <option value="">{catalogLoading ? 'Loading sessions…' : 'Choose a session'}</option>{sessions.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <label>Semester<select value={semester} disabled={busy} onChange={(e) => { invalidate(); setSemester(e.target.value); }}><option value="harmattan">Harmattan</option><option value="rain">Rain</option></select></label></div>
      {!catalogLoading && !sessions.length && !catalogError && <Empty>No academic sessions are available. Add the session in academic administration first.</Empty>}
      <label><input type="checkbox" checked={isRevised} disabled={busy} onChange={e=>{invalidate();setIsRevised(e.target.checked);}}/> This is a revised result</label>{isRevised&&<label>Internal revision reason<textarea value={revisionReason} onChange={e=>{invalidate();setRevisionReason(e.target.value);}} required maxLength={1000}/><span>The reason is retained internally and never included in guardian emails or PDFs.</span></label>}
      <StudentPicker api={api} selected={selected} toggle={toggleStudent} disabled={busy} />
      <div className="selected"><strong>{students.length} selected</strong><div className="chips">{students.map((row) => <button key={row.student_id} disabled={busy} onClick={() => toggleStudent(row)} aria-label={`Remove ${row.full_name}`}>{row.full_name} ×</button>)}</div></div>
      <div className="actions"><button className="primary" disabled={busy || !students.length || !session || !!catalogError} onClick={preview}>{busy ? 'Preparing…' : 'Preview guardian emails'}</button><span>Previewing sends nothing.</span></div>
    </section>{!!students.length && <Preferences api={api} students={students} busy={busy} setBusy={setBusy} invalidate={invalidate} />}</>}
    {panel === 'review' && (batch ? <BatchReview batch={batch} busy={busy} reviewed={reviewed} setReviewed={setReviewed} send={send} retry={retry} refresh={() => refresh()} /> : <Empty>{busy ? 'Loading batch…' : 'Select a batch from history or prepare a new preview.'}</Empty>)}
    {panel === 'history' && <History api={api} load={loadHistory} disabled={busy} sessions={sessions} />}
  </>;
}

function StudentPicker({ api, selected, toggle, disabled }) {
  const [query, setQuery] = useState(''), [term, setTerm] = useState('');
  const [level, setLevel] = useState(''), [active, setActive] = useState(true);
  const [page, setPage] = useState(1), [reload, setReload] = useState(0);
  const loadStudents = useCallback(() => {
    const params = { page, ...(query ? { search: query } : {}), ...(level ? { current_level: level } : {}), ...(active ? { is_active: 'true' } : {}) };
    return api.students(params);
  }, [api, query, level, active, page]);
  const resource = useRemote(loadStudents, reload);
  const { data, loading } = resource;
  const error = resource.error?.message || '';
  return <><form className="filters" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(term.trim()); }}>
    <label className="grow">Find a student<input type="search" value={term} placeholder="Name or matric number" disabled={disabled} onChange={(e) => setTerm(e.target.value)} /></label><button disabled={disabled}>Search</button>
    <label>Level<select value={level} disabled={disabled} onChange={(e) => { setLevel(e.target.value); setPage(1); }}><option value="">All levels</option>{[100, 200, 300, 400, 500].map((n) => <option key={n}>{n}</option>)}</select></label>
    <label className="check"><input type="checkbox" checked={active} disabled={disabled} onChange={(e) => { setActive(e.target.checked); setPage(1); }} />Active students only</label></form>
    <Alert>{error}</Alert>{error && <button onClick={() => setReload((n) => n + 1)}>Retry student list</button>}
    {loading ? <Empty>Loading students…</Empty> : data?.results?.length ? <div className="table-wrap"><table><caption className="sr-only">Students available for result sharing</caption><thead><tr><th>Select</th><th>Student</th><th>Identifier</th><th>Level</th></tr></thead>
      <tbody>{data.results.map((row) => <tr key={row.student_id}><td><input type="checkbox" aria-label={`Select ${row.full_name}`} checked={!!selected[row.student_id]} disabled={disabled || (!selected[row.student_id] && Object.keys(selected).length >= 100)} onChange={() => toggle(row)} /></td><td>{row.full_name}</td><td>{row.identifier_value}</td><td>{row.current_level}</td></tr>)}</tbody></table></div> : !error && <Empty>No students match these filters.</Empty>}
    <Pager page={page} next={data?.next} onChange={setPage} disabled={disabled || loading} />
  </>;
}

function Preferences({ api, students, busy, setBusy, invalidate }) {
  const [studentId, setStudentId] = useState('');
  const effectiveId = students.some((row) => row.student_id === studentId) ? studentId : '';
  return <section className="card"><p className="eyebrow">Recipient permissions</p><h2>Guardian email sharing</h2><p>Record the actual sharing permission or withdrawal. An email address alone does not enable reports.</p>
    <label>Student<select value={effectiveId} disabled={busy} onChange={(e) => setStudentId(e.target.value)}><option value="">Choose a selected student</option>{students.map((row) => <option key={row.student_id} value={row.student_id}>{row.full_name}</option>)}</select></label>
    {effectiveId && <PreferenceRows key={effectiveId} api={api} effectiveId={effectiveId} busy={busy} setBusy={setBusy} invalidate={invalidate} />}
  </section>;
}

function PreferenceRows({ api, effectiveId, busy, setBusy, invalidate }) {
  const [updates, setUpdates] = useState({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const load = useCallback(async () => {
    const guardians = await api.guardians(effectiveId);
    return Promise.all(guardians.map(async guardian => ({ ...guardian, preference: await api.preference(effectiveId, guardian.guardian_id) })));
  }, [api, effectiveId]);
  const resource = useRemote(load);
  const rows = (resource.data || []).map(row => ({ ...row, preference: updates[row.guardian_id] || row.preference }));
  async function save(guardian, preference) {
    invalidate(); setBusy(true); setError(''); setNotice('');
    try {
      const saved = await api.savePreference(effectiveId, guardian.guardian_id, preference);
      setUpdates(old => ({ ...old, [guardian.guardian_id]: saved }));
      setNotice('Sharing permission saved. Prepare a fresh preview before sending.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <><Alert>{error || resource.error?.message}</Alert>{notice && <p className="notice" role="status">{notice}</p>}
    {resource.error && <button onClick={resource.retry}>Retry guardian permissions</button>}
    {resource.loading ? <Empty>Loading guardian permissions…</Empty> : !error && !resource.error && !rows.length ? <Empty>No guardians are recorded. Add their details in student administration first.</Empty> : rows.map((row) => <GuardianPermission key={`${row.guardian_id}-${row.preference.updated_at}`} guardian={row} disabled={busy} save={save} />)}
  </>;
}

function GuardianPermission({ guardian, disabled, save }) {
  const [enabled, setEnabled] = useState(guardian.preference.email_enabled);
  const [evidence, setEvidence] = useState(guardian.preference.evidence);
  return <form className="permission" onSubmit={(e) => { e.preventDefault(); save(guardian, { email_enabled: enabled, whatsapp_enabled: guardian.preference.whatsapp_enabled, evidence: evidence.trim() }); }}>
    <h3>{guardian.full_name}</h3><p>{guardian.relationship} · {guardian.email || 'Email address missing'}</p>
    <label className="check"><input type="checkbox" checked={enabled} disabled={disabled} onChange={(e) => setEnabled(e.target.checked)} />Enable result emails for this guardian</label>
    <label>Basis of permission or withdrawal<textarea required maxLength={2000} value={evidence} disabled={disabled} onChange={(e) => setEvidence(e.target.value)} /></label>
    <button disabled={disabled || !evidence.trim()}>Save sharing permission</button>
  </form>;
}

export function BatchReview({ batch, busy, reviewed, setReviewed, send, retry, refresh }) {
  const draft = batch.counts?.draft || 0;
  const emailOnly = batch.deliveries.every((row) => row.channel === 'email');
  const retryable = batch.deliveries.some((row) => row.status === 'failed' && row.attempts < 3);
  return <section className="card"><div className="section-heading"><div><p className="eyebrow">02 / Review before sending</p><h2>{batch.queued_at ? 'Batch progress' : 'Report preview'}</h2></div><button onClick={refresh} disabled={busy}>Refresh status</button></div>
    <div className="counts">{Object.entries(batch.counts).map(([status, count]) => <div key={status}><strong>{count}</strong><span>{statuses[status] || status}</span></div>)}</div>
    {!!batch.counts.unknown && <Alert>Some submissions have an uncertain outcome. Check with the sender/provider before making any new batch for those recipients. These submissions are not automatically retried.</Alert>}
    <p className="hint">Accepted by provider means the mail server accepted the message. It does not confirm that it reached the guardian’s inbox.</p>
    {!emailOnly && <Alert>This batch includes another channel. Its progress is available here; use its original sharing workflow to queue or retry it.</Alert>}
    {batch.preview.map((student) => <article className="report" key={student.student_id}><div className="section-heading"><h3>{student.name}</h3><span>{student.identifier}</span></div>
      {student.diagnostic_code && <p className="warning">{reason(student.diagnostic_code)}</p>}
      {student.report && <details><summary>Read verified result report</summary><pre>{student.report.text}</pre></details>}
      <ul className="recipients">{student.recipients.map((recipient, index) => <li key={`${recipient.guardian_id}-${recipient.channel}-${index}`}><div><strong>{recipient.guardian_name}</strong><span>{recipient.destination || 'Contact missing'} · {recipient.channel}</span></div><span className={recipient.diagnostic_code ? 'warning' : 'eligible'}>{recipient.diagnostic_code ? reason(recipient.diagnostic_code) : 'Eligible'}</span></li>)}</ul>
    </article>)}
    {!batch.queued_at && <div className="send-box"><label className="check"><input type="checkbox" checked={reviewed} disabled={busy || !draft} onChange={(e) => setReviewed(e.target.checked)} />I have reviewed the reports, recipients and skipped entries.</label>
      <button className="primary" disabled={busy || !reviewed || !draft || !emailOnly} onClick={send}>{busy ? 'Submitting…' : `Send ${draft} ${draft === 1 ? 'email' : 'emails'}`}</button>
      {!draft && <p>No eligible emails. Resolve the listed issues and prepare a fresh preview.</p>}</div>}
    {!!batch.deliveries.length && <details className="delivery-details"><summary>Individual submission status</summary><div className="table-wrap"><table><thead><tr><th>Recipient</th><th>Channel</th><th>Status</th><th>Attempts</th><th>Details</th></tr></thead><tbody>{batch.deliveries.map((row) => <tr key={row.id}><td>{row.destination || 'Contact missing'}</td><td>{row.channel}</td><td>{statuses[row.status] || row.status}</td><td>{row.attempts}</td><td>{reason(row.diagnostic_code)}</td></tr>)}</tbody></table></div></details>}
    {retryable && emailOnly && <div className="actions"><button disabled={busy} onClick={retry}>Retry failed submissions</button><span>Accepted and uncertain submissions are excluded.</span></div>}
  </section>;
}

function History({ api, load, disabled, sessions }) {
  const [page, setPage] = useState(1), [reload, setReload] = useState(0);
  const loadHistory = useCallback(() => api.history(page), [api, page]);
  const resource = useRemote(loadHistory, reload);
  const { data, loading } = resource;
  const error = resource.error?.message || '';
  return <section className="card"><p className="eyebrow">Correspondence register</p><h2>Batch history</h2><p>Open a saved batch to review reports and follow its submissions.</p><Alert>{error}</Alert>{error && <button onClick={() => setReload((n) => n + 1)}>Retry history</button>}
    {loading ? <Empty>Loading batches…</Empty> : data?.results?.length ? <div className="history">{data.results.map((row) => <button disabled={disabled} key={row.id} onClick={() => load(row.id)}><span><strong>{sessions.find((item) => item.id === row.academic_session)?.name || 'Academic session'} · {row.semester}</strong><small>{new Date(row.created_at).toLocaleString()} · {row.queued_at ? 'Queued' : 'Draft'}</small></span><span>{Object.entries(row.counts).map(([status, count]) => `${count} ${statuses[status] || status}`).join(' · ')} →</span></button>)}</div> : !error && <Empty>No batches yet. Start by choosing students and preparing a preview.</Empty>}
    <Pager page={page} next={data?.next} onChange={setPage} disabled={disabled || loading} /></section>;
}
