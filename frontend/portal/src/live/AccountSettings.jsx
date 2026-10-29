import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../api';
import { useAuth } from '../auth/useAuth';
import { Alert, Empty, Pager, RemoteState, Table } from './ui';
import { isHod, useRemote } from './resources';

function PasswordSettings() {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget, values = new FormData(form);
    if (values.get('password') !== values.get('confirm')) { setError('The new passwords do not match.'); return; }
    setBusy(true); setError(''); setNotice('');
    try { await api.changePassword(values.get('current'), values.get('password')); form.reset(); setNotice('Your password has been changed.'); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="live-card" id="account-password"><h2>Change password</h2><Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}
    <form className="live-form" onSubmit={submit}><label>Current password<input name="current" type="password" autoComplete="current-password" required disabled={busy} /></label>
      <label>New password<input name="password" type="password" autoComplete="new-password" required disabled={busy} /></label>
      <label>Confirm new password<input name="confirm" type="password" autoComplete="new-password" required disabled={busy} /></label>
      <button className="live-primary" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button></form></section>;
}

export default function AccountSettings({ user }) {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [administrationSuspended, setAdministrationSuspended] = useState(false);
  const [roleMessage, setRoleMessage] = useState(''), [checkingRole, setCheckingRole] = useState(false);
  async function checkRole(confirmedTransfer = false) {
    setAdministrationSuspended(true); setCheckingRole(true);
    setRoleMessage(confirmedTransfer ? 'HOD responsibility transferred. Checking your current account…' : 'The transfer outcome is uncertain. Checking your current account without sending the transfer again…');
    try {
      const identity = await api.getCurrentUser();
      if (isHod(identity)) {
        setRoleMessage('Your account currently still shows HOD access. Confirm the department’s HOD status before making another transfer. This request has not been resent.');
      } else {
        const refreshed = await refreshUser();
        navigate(refreshed ? `/portal/${refreshed.role}/account` : '/login', { replace: true });
        setRoleMessage('Your current account access has been refreshed. HOD controls are no longer available here.');
      }
    } catch {
      setRoleMessage('The current HOD status could not be confirmed. Department controls are locked. Check the current account again before any further changes.');
    } finally { setCheckingRole(false); }
  }
  return <>
    <section className="live-card"><h2>Your account</h2><p>Choose a setting below.</p><nav className="live-downloads" aria-label="Account settings sections"><a href="#account-password">Password</a>{isHod(user) && !administrationSuspended && <><a href="#account-staff">Staff accounts</a><a href="#account-advisers">Part-advisers</a><a href="#account-hod-transfer">HOD transfer</a></>}</nav></section>
    <PasswordSettings />
    {roleMessage && <section className="live-card"><h2>Current account status</h2><p role="status">{roleMessage}</p><button disabled={checkingRole} onClick={() => checkRole(false)}>{checkingRole ? 'Checking account…' : 'Check current account'}</button></section>}
    {isHod(user) && !administrationSuspended && <DepartmentSettings user={user} onTransferOutcome={checkRole} />}
  </>;
}

const staffLabel = (staff) => `${[staff.first_name, staff.last_name].filter(Boolean).join(' ') || staff.username} (${staff.username})`;
const permissionCode = (permission) => typeof permission === 'string' ? permission : permission.code;
const uncertainMessage = (error) => error.status === 0 || error.status >= 500 ? `${error.message} The outcome is uncertain. Refresh the relevant list and check the saved record before trying another change.` : error.message;

function DepartmentSettings({ user, onTransferOutcome }) {
  const [revision, setRevision] = useState(0);
  const options = useRemote((signal) => api.getAdministrationOptions(signal), [user.id]);
  const staffChoices = useRemote((signal) => api.collectPages((page, pageSignal) => api.listManagedStaff({ page, is_active: true }, pageSignal), signal), [user.id, revision]);
  function changed() { setRevision((value) => value + 1); }
  return <>
    <section className="live-card" id="account-staff"><h2>Department settings</h2><p>Manage staff access and part-adviser responsibilities. HOD responsibility is transferred separately below.</p>
      <RemoteState resource={options}>{(configuration) => <StaffSettings user={user} configuration={configuration} onChanged={changed} />}</RemoteState>
    </section>
    <section className="live-card" id="account-advisers"><h2>Part-adviser assignments</h2><p>Assign or reassign an academic level for a recorded session. Deactivating an assignment removes that adviser scope.</p>
      <RemoteState resource={options}>{(configuration) => <RemoteState resource={staffChoices}>{(staff) => <AdviserSettings configuration={configuration} staff={staff} />}</RemoteState>}</RemoteState>
    </section>
    <section className="live-card" id="account-hod-transfer"><h2>Transfer HOD responsibility</h2><p>Select an existing active staff account. The selected person must accept the offer in Documents and requests before HOD access changes.</p>
      <RemoteState resource={staffChoices}>{(staff) => <HodTransfer user={user} staff={staff} onTransferOutcome={onTransferOutcome} />}</RemoteState>
    </section>
  </>;
}

function StaffSettings({ user, configuration, onChanged }) {
  const [page, setPage] = useState(1), [search, setSearch] = useState('');
  const [editor, setEditor] = useState(null);
  const staff = useRemote((signal) => api.listManagedStaff({ page, search }, signal), [page, search]);
  function saved() { setEditor(null); staff.reload(); onChanged(); }
  return <>
    <div className="live-row"><h3>Staff accounts</h3><button onClick={() => setEditor({})}>Add staff member</button></div>
    <form className="live-filters" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(new FormData(event.currentTarget).get('search')); }}><label>Find staff<input name="search" type="search" placeholder="Name or username" /></label><button>Search staff</button><button type="button" onClick={staff.reload}>Refresh staff list</button></form>
    <RemoteState resource={staff}>{(data) => <>{!data.results.length ? <Empty>No staff accounts match this search.</Empty> : <Table headings={['Staff member', 'Email', 'Access', 'Edit']}>
      {data.results.map((row) => <tr key={row.id}><td>{staffLabel(row)}</td><td>{row.email || 'Not supplied'}</td><td>{row.is_hod ? 'HOD' : row.is_active ? 'Active staff' : 'Inactive staff'}</td><td>{row.is_hod || row.id === user.id ? <span>Use account password settings or HOD transfer.</span> : <button onClick={() => setEditor(row)}>Edit {row.username}</button>}</td></tr>)}
    </Table>}<Pager page={page} data={data} onChange={setPage} /></>}</RemoteState>
    {editor && <StaffEditor key={editor.id || 'new'} staff={editor} configuration={configuration} onSaved={saved} onCancel={() => setEditor(null)} />}
  </>;
}

function StaffEditor({ staff, configuration, onSaved, onCancel }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const editing = !!staff.id;
  const direct = (staff.direct_permissions || []).map(permissionCode);
  const inherited = (staff.inherited_permissions || []).map(permissionCode);
  const catalogue = configuration.permissions || [];
  async function submit(event) {
    event.preventDefault(); const form = event.currentTarget, values = new FormData(form);
    const body = { first_name: values.get('first_name'), last_name: values.get('last_name'), email: values.get('email'), is_active: values.has('is_active'), permission_codes: values.getAll('permission_codes') };
    if (!editing) { body.username = values.get('username'); body.password = values.get('password'); }
    setBusy(true); setError('');
    try { if (editing) await api.updateManagedStaff(staff.id, body); else await api.createManagedStaff(body); onSaved(); }
    catch (err) { setError(uncertainMessage(err)); }
    finally { if (form.elements.password) form.elements.password.value = ''; setBusy(false); }
  }
  return <div className="live-inset"><h3>{editing ? `Edit staff: ${staff.username}` : 'New staff account'}</h3><Alert>{error}</Alert>
    <form className="live-form" onSubmit={submit}>
      {!editing && <><label>Staff username<input name="username" maxLength="150" autoComplete="off" required disabled={busy} /></label><label>Initial password<input name="password" type="password" autoComplete="new-password" required disabled={busy} /></label></>}
      <label>First name<input name="first_name" defaultValue={staff.first_name || ''} maxLength="150" disabled={busy} /></label>
      <label>Last name<input name="last_name" defaultValue={staff.last_name || ''} maxLength="150" disabled={busy} /></label>
      <label>Staff email<input name="email" type="email" defaultValue={staff.email || ''} disabled={busy} /></label>
      <label className="live-check"><input name="is_active" type="checkbox" defaultChecked={staff.is_active ?? true} disabled={busy} />Staff account is active</label>
      <fieldset className="live-wide"><legend>Direct staff permissions</legend><p className="live-hint">Choose the tasks this staff member may perform. Group permissions remain in effect and are shown separately.</p>
        {catalogue.map((permission) => <label className="live-check" key={permission.code}><input name="permission_codes" value={permission.code} type="checkbox" defaultChecked={direct.includes(permission.code)} disabled={busy} />{permission.label}</label>)}
      </fieldset>
      {!!inherited.length && <div className="live-wide"><h4>Permissions inherited from groups</h4><p>{inherited.map((code) => catalogue.find((permission) => permission.code === code)?.label || code).join(', ')}</p><p className="live-hint">These are read-only here. Removing a direct permission does not remove the same permission granted by a group.</p></div>}
      {!editing && <p className="live-hint">Share the initial password privately. This action does not send an email or require a password change at first sign-in.</p>}
      <button className="live-primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save staff changes' : 'Create staff account'}</button><button type="button" disabled={busy} onClick={onCancel}>Cancel staff edit</button>
    </form>
  </div>;
}

function AdviserSettings({ configuration, staff }) {
  const [page, setPage] = useState(1), [session, setSession] = useState(''), [editor, setEditor] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const assignments = useRemote((signal) => api.listAdviserAssignments({ page, academic_session: session }, signal), [page, session]);
  const eligibleStaff = staff.filter((member) => !member.is_hod);
  async function deactivate(row) {
    setBusy(true); setError('');
    try { await api.updateAdviserAssignment(row.id, { is_active: false }); assignments.reload(); }
    catch (err) { setError(uncertainMessage(err)); }
    finally { setBusy(false); }
  }
  return <>
    <div className="live-row"><button disabled={busy || !configuration.academic_sessions?.length || !eligibleStaff.length} onClick={() => setEditor({ academic_session: configuration.current_academic_session || '', is_active: true })}>Assign part-adviser</button><button disabled={busy} onClick={assignments.reload}>Refresh adviser assignments</button></div>
    <label>Filter adviser session<select value={session} disabled={busy} onChange={(event) => { setSession(event.target.value); setPage(1); }}><option value="">All recorded sessions</option>{configuration.academic_sessions?.map((period) => <option key={period.id} value={period.name}>{period.name}</option>)}</select></label>
    {!configuration.academic_sessions?.length && <p>Record an academic session before assigning a part-adviser.</p>}
    <Alert>{error}</Alert><RemoteState resource={assignments}>{(data) => <>{!data.results.length ? <Empty>No part-adviser assignments are recorded.</Empty> : <Table headings={['Staff member', 'Session', 'Level', 'Status', 'Manage']}>
      {data.results.map((row) => <tr key={row.id}><td>{staff.find((member) => member.id === row.staff_id) ? staffLabel(staff.find((member) => member.id === row.staff_id)) : row.staff_username}</td><td>{row.academic_session}</td><td>{row.level}</td><td>{row.is_active ? 'Active' : 'Inactive'}</td><td><button disabled={busy} onClick={() => setEditor(row)}>Edit assignment for {row.staff_username} · {row.level}</button>{row.is_active && <button disabled={busy} onClick={() => deactivate(row)}>Deactivate {row.staff_username} · {row.level}</button>}</td></tr>)}
    </Table>}<Pager page={page} data={data} onChange={setPage} disabled={busy} /></>}</RemoteState>
    {editor && <AdviserEditor key={editor.id || 'new'} assignment={editor} configuration={configuration} staff={eligibleStaff} onSaved={() => { setEditor(null); assignments.reload(); }} onCancel={() => setEditor(null)} />}
  </>;
}

function AdviserEditor({ assignment, configuration, staff, onSaved, onCancel }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const previousOwnerUnavailable = assignment.staff_id && !staff.some((member) => member.id === assignment.staff_id);
  async function submit(event) {
    event.preventDefault(); const values = new FormData(event.currentTarget);
    const body = { staff_id: Number(values.get('staff_id')), academic_session: values.get('academic_session'), level: Number(values.get('level')), is_active: values.has('is_active') };
    setBusy(true); setError('');
    try { if (assignment.id) await api.updateAdviserAssignment(assignment.id, body); else await api.createAdviserAssignment(body); onSaved(); }
    catch (err) { setError(uncertainMessage(err)); }
    finally { setBusy(false); }
  }
  return <div className="live-inset"><h3>{assignment.id ? 'Edit part-adviser assignment' : 'New part-adviser assignment'}</h3><Alert>{error}</Alert><form className="live-form" onSubmit={submit}>
    {previousOwnerUnavailable && <p className="live-hint">The current owner is no longer eligible for an active adviser assignment. Select an eligible staff member to reassign, or deactivate this assignment from its row above.</p>}
    <label>Assigned staff member<select name="staff_id" defaultValue={previousOwnerUnavailable ? '' : assignment.staff_id || ''} required disabled={busy}><option value="">{previousOwnerUnavailable ? `${assignment.staff_username} — choose a new eligible staff member` : 'Choose a staff member'}</option>{staff.map((member) => <option key={member.id} value={member.id}>{staffLabel(member)}</option>)}</select></label>
    <label>Assignment academic session<select name="academic_session" defaultValue={assignment.academic_session || ''} required disabled={busy}><option value="">Choose a recorded session</option>{configuration.academic_sessions?.map((period) => <option key={period.id} value={period.name}>{period.name}</option>)}</select></label>
    <label>Assigned level<input name="level" type="number" min="1" max="32767" defaultValue={assignment.level || ''} placeholder="e.g. 300" required disabled={busy} /></label>
    <label className="live-check"><input name="is_active" type="checkbox" defaultChecked={assignment.is_active ?? true} disabled={busy} />Adviser assignment is active</label>
    <button className="live-primary" disabled={busy}>{busy ? 'Saving…' : 'Save adviser assignment'}</button><button type="button" disabled={busy} onClick={onCancel}>Cancel assignment edit</button>
  </form></div>;
}

function HodTransfer({ user, staff, onTransferOutcome }) {
  const [targetId, setTargetId] = useState(''), [expected, setExpected] = useState('');
  const [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const targets = staff.filter((member) => member.can_transfer && member.is_active && !member.is_hod && member.id !== user.id);
  const target = targets.find((member) => String(member.id) === targetId);
  const ready = target && expected === target.username && reviewed && !busy && !notice;
  function chooseTarget(event) {
    setTargetId(event.target.value); setExpected(''); setReviewed(false); setError(''); setNotice('');
  }
  async function submit(event) {
    event.preventDefault(); if (!ready) return;
    setBusy(true); setError('');
    try {
      await api.apiRequest('/api/workflows/handover/', { method: 'POST', body: { target_id: target.id } });
      setNotice('Handover offered. Your HOD access remains until the incoming staff member accepts in Documents and requests.');
      setReviewed(false);
    } catch (err) {
      if (err.status === 0 || err.status >= 500 || err.status === 403) await onTransferOutcome(false);
      else { setError(err.message); setReviewed(false); }
    } finally { setBusy(false); }
  }
  return <>
    {!targets.length ? <Empty>No eligible active staff member is available. Create or activate a staff account first.</Empty> : <form className="live-form" onSubmit={submit}>
      <label>New HOD<select value={targetId} onChange={chooseTarget} disabled={busy} required><option value="">Choose an existing staff member</option>{targets.map((member) => <option key={member.id} value={member.id}>{staffLabel(member)}</option>)}</select></label>
      {target && <>
        <p className="live-notice">{staffLabel(target)} will be offered HOD responsibility. Your access changes only after their acceptance. Adviser assignments remain separate.</p>
        <label>Type the new HOD’s username<input value={expected} onChange={(event) => { setExpected(event.target.value); setReviewed(false); }} autoComplete="off" required disabled={busy} /></label>
        <label className="live-check"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} disabled={busy} />I reviewed the selected staff member and understand that access changes only after acceptance.</label>
        <button className="live-primary" disabled={!ready}>{busy ? 'Offering handover…' : 'Offer HOD handover'}</button>
      </>}
    </form>}
    <Alert>{error}</Alert>{notice && <p role="status">{notice}</p>}
  </>;
}
