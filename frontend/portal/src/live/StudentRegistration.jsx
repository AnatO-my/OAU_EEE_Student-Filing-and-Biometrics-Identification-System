import { useRef, useState } from 'react';
import * as api from '../api';
import { Alert } from './ui';
import { hasPermission, isHod } from './resources';

export default function StudentRegistration({ user, onCreated, initialIdentifier = '', initialIdentifierType = 'matriculation' }) {
  const [identifierType, setIdentifierType] = useState(initialIdentifierType === 'utme' ? 'utme' : 'matriculation');
  const [identifier, setIdentifier] = useState(initialIdentifier);
  const [checked, setChecked] = useState(''), [match, setMatch] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const request = useRef(0);
  const levels = [...new Set(user.adviser_levels || [])].sort((a, b) => a - b);
  const allowed = hasPermission(user, 'students.add_student') && hasPermission(user, 'students.view_student') && (isHod(user) || levels.length > 0);
  if (!allowed) return null;
  const key = `${identifierType}:${identifier.trim()}`;
  function changeIdentifier(type, value) {
    request.current += 1; setIdentifierType(type); setIdentifier(value); setChecked(''); setMatch(null); setError(''); setNotice('');
  }
  async function lookup(event) {
    event.preventDefault(); const started = ++request.current;
    setBusy(true); setError(''); setNotice(''); setChecked(''); setMatch(null);
    try {
      const student = await api.lookupStudentIdentifier(identifierType, identifier.trim());
      if (started !== request.current) return;
      setMatch(student); setChecked(key);
    } catch (err) {
      if (started !== request.current) return;
      if (err.status === 404) { setChecked(key); setNotice('No matching student is available in your scope. Complete the approved registration below.'); }
      else setError(err.message);
    } finally { if (started === request.current) setBusy(false); }
  }
  async function register(event) {
    event.preventDefault(); if (checked !== key || match || busy) return;
    const form = event.currentTarget, values = Object.fromEntries(new FormData(form));
    setBusy(true); setError(''); setNotice('');
    try {
      const student = await api.createStudent({ ...values, identifier_type: identifierType, identifier_value: identifier.trim(), admission_year: Number(values.admission_year), current_level: Number(values.current_level) });
      setMatch(student); setNotice('Student registered. No login account was created.'); form.reset(); onCreated?.(student);
    } catch (err) {
      setChecked(''); setError(`${err.message} Check this identifier again before another registration attempt.`);
    } finally { setBusy(false); }
  }
  return <section className="live-card live-registration"><details open={!!initialIdentifier}><summary>Register student</summary><p>Check the matriculation or UTME number first. One student record is shared across all courses and sessions.</p><Alert>{error}</Alert>{notice && <p className="live-notice" role="status">{notice}</p>}
    <form className="live-filters" onSubmit={lookup}>
      <label>Identifier type<select value={identifierType} disabled={busy} onChange={(event) => changeIdentifier(event.target.value, identifier)}><option value="matriculation">Matriculation number</option><option value="utme">UTME number</option></select></label>
      <label>Student identifier<input value={identifier} onChange={(event) => changeIdentifier(identifierType, event.target.value)} autoComplete="off" maxLength="100" required disabled={busy} /></label>
      <button disabled={busy || !identifier.trim()}>{busy ? 'Checking…' : 'Check identifier'}</button>
    </form>
    {match && <div className="live-notice"><strong>Existing student: {match.full_name}</strong><p>{match.identifier_value} · Level {match.current_level}</p><button onClick={() => onCreated?.(match)}>Open existing student</button></div>}
    {checked === key && !match && <form className="live-form" onSubmit={register}>
      <label>Full name<input name="full_name" maxLength="200" required disabled={busy} /></label>
      <label>Surname (optional)<input name="surname" maxLength="100" disabled={busy} autoComplete="off" /></label>
      <label>Phone number (optional)<input name="phone_number" type="tel" maxLength="30" disabled={busy} /></label>
      <label>Admission year<input name="admission_year" type="number" min="1" max="32767" required disabled={busy} /></label>
      <label>Admission mode<select name="mode_of_admission" disabled={busy}><option value="utme">UTME</option><option value="direct_entry">Direct Entry</option><option value="transfer">Transfer</option></select></label>
      <label>Current level{isHod(user) ? <input name="current_level" type="number" min="1" max="32767" required disabled={busy} /> : <select name="current_level" disabled={busy}>{levels.map((level) => <option key={level} value={level}>{level}</option>)}</select>}</label>
      <p className="live-hint">Leave unknown optional details empty. Student login accounts are provisioned separately by the HOD.</p>
      <button className="live-primary" disabled={busy}>{busy ? 'Registering…' : 'Register approved student'}</button>
    </form>}
  </details><p className="live-hint">For new arrivals and approved student records not yet in the directory.</p></section>;
}

export function StudentProfileEditor({ row, user, onSaved }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  if (!hasPermission(user, 'students.change_student')) return null;
  async function submit(event) {
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget));
    if (!values.surname) delete values.surname;
    if (values.admission_year) values.admission_year = Number(values.admission_year);
    setBusy(true); setError('');
    try { await api.updateStudent(row.student_id, values); onSaved(); }
    catch (err) { setError(`${err.message} Reload the record before retrying a change with an uncertain outcome.`); }
    finally { setBusy(false); }
  }
  return <details><summary>Complete or correct student details</summary><Alert>{error}</Alert><form className="live-form" onSubmit={submit}>
    <label>Full name<input name="full_name" defaultValue={row.full_name} maxLength="200" required disabled={busy} /></label>
    <label>Set surname (leave blank to keep existing)<input name="surname" autoComplete="off" maxLength="100" disabled={busy} /></label>
    <label>Phone number (optional)<input name="phone_number" defaultValue={row.phone_number || ''} type="tel" maxLength="30" disabled={busy} /></label>
    <label>Admission year<input name="admission_year" defaultValue={row.admission_year} type="number" min="1" max="32767" required disabled={busy} /></label>
    <label>Admission mode<select name="mode_of_admission" defaultValue={row.mode_of_admission} disabled={busy}><option value="utme">UTME</option><option value="direct_entry">Direct Entry</option><option value="transfer">Transfer</option></select></label>
    <p className="live-hint">Identifier conversion and current-level changes are controlled separately. A surname is never guessed from the full name.</p>
    <button className="live-primary" disabled={busy}>{busy ? 'Saving…' : 'Save student details'}</button>
  </form></details>;
}

export function PromoteIdentifier({ row, user, onSaved }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  if (!isHod(user) || row.identifier_type !== 'utme') return null;
  async function submit(event) {
    event.preventDefault(); const values = new FormData(event.currentTarget); setBusy(true); setError('');
    try { await api.promoteStudentIdentifier(row.student_id, values.get('matriculation'), row.identifier_type, row.identifier_value); onSaved(); }
    catch (err) { setError(`${err.message} Reload the student before another conversion attempt.`); }
    finally { setBusy(false); }
  }
  return <details><summary>Assign matriculation number</summary><p>Keep this student’s record, account and results. The former UTME number remains a lookup reference.</p><Alert>{error}</Alert><form className="live-form" onSubmit={submit}>
    <label>Assigned matriculation number<input name="matriculation" required maxLength="100" disabled={busy} /></label>
    <label className="live-check"><input type="checkbox" required disabled={busy} /> I checked this matriculation number against the approved student record.</label>
    <button disabled={busy}>{busy ? 'Assigning…' : 'Assign reviewed matriculation number'}</button>
  </form></details>;
}
