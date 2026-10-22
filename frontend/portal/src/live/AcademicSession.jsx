import { useState } from 'react';
import { collectPages, getCurrentAcademicSession, listAcademicSessions, selectCurrentAcademicSession } from '../api';
import { Alert, RemoteState } from './ui';
import { useRemote } from './resources';

export default function AcademicSession() {
  const resource = useRemote(async (signal) => {
    const [current, sessions] = await Promise.all([getCurrentAcademicSession(signal), collectPages(listAcademicSessions, signal)]);
    return { current, sessions };
  }, []);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try { await selectCurrentAcademicSession(Number(values.get('session')), resource.data.current.academic_session); resource.reload(); }
    catch (err) { setError(`${err.message} Reload the current session before trying another change.`); }
    finally { setBusy(false); }
  }
  return <section className="live-card"><h2>Current academic session</h2><Alert>{error}</Alert><RemoteState resource={resource}>{({ current, sessions }) => <>
    <p>Current: <strong>{current.name || 'Not selected'}</strong> · Source: {current.source}</p>
    <p>This sets the period used for adviser scope and attendance. Review assignments and rosters separately before opening classes.</p>
    <form className="live-form" onSubmit={submit}><label>Academic session<select name="session" defaultValue={current.academic_session || ''} required disabled={busy}>
      <option value="">Choose a session</option>{sessions.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label className="live-check"><input type="checkbox" required disabled={busy} /> I reviewed the academic session and its effect on staff access.</label>
      <button disabled={busy || !sessions.length} className="live-primary">{busy ? 'Selecting…' : 'Set current session'}</button></form>
    <button onClick={resource.reload} disabled={busy}>Reload current session</button>
    {!sessions.length && <p>Add an academic session in <a href="/admin/academics/academicsession/">academic administration</a> first.</p>}</>}</RemoteState></section>;
}
