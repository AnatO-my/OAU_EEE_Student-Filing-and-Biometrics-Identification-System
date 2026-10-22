import { useState } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api';
import { Alert, RemoteState } from './ui';
import { isHod, useRemote } from './resources';

export default function StudentLogin({ user, studentId, identifierValue, identifierType = 'matriculation', studentActive = true }) {
  if (!isHod(user)) return null;
  return <StudentLoginPanel key={`${user.id}:${studentId}`} studentId={studentId} identifierValue={identifierValue} identifierType={identifierType} studentActive={studentActive} />;
}

function StudentLoginPanel({ studentId, identifierValue, identifierType, studentActive }) {
  const resource = useRemote((signal) => api.getStudentLoginAccount(studentId, signal), [studentId]);
  const [secret, setSecret] = useState(null), [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [uncertain, setUncertain] = useState(false), [checked, setChecked] = useState(false), [forbidden, setForbidden] = useState(false);
  const [emailUncertain, setEmailUncertain] = useState(false);
  const [reissueReviewed, setReissueReviewed] = useState(false);
  function refresh() {
    setSecret(null); setRevealed(false); setNotice(''); setReissueReviewed(false); setChecked(true); resource.reload();
  }
  async function issue(event, account) {
    event.preventDefault(); if (busy || forbidden || !studentActive || (account && (!reissueReviewed || (uncertain && !checked))) || (!account && uncertain)) return;
    const values = new FormData(event.currentTarget);
    const body = account ? {} : { username: values.get('username').trim(), email: values.get('email').trim() };
    setBusy(true); setError(''); setNotice(''); setSecret(null); setRevealed(false); setReissueReviewed(false);
    try {
      const result = await api.issueStudentSetupLink(studentId, body);
      if (!result?.account || typeof result.uid !== 'string' || !result.uid || typeof result.token !== 'string' || !result.token || !Number.isFinite(result.expires_in) || result.expires_in <= 0) {
        throw new TypeError('The setup response could not be verified.');
      }
      const link = new URL('/setup-student', window.location.origin);
      link.hash = new URLSearchParams({ uid: result.uid, token: result.token }).toString();
      setSecret({ url: link.href, expiresIn: result.expires_in }); setUncertain(false); setEmailUncertain(false); setChecked(false);
      setNotice('Private setup link created. The student chooses their own password.'); resource.reload();
    } catch (err) {
      const unknown = ![400, 403, 404, 409, 429].includes(err.status);
      setUncertain(unknown); setChecked(false);
      if (err.status === 403) setForbidden(true);
      setError(unknown ? 'The account request may have succeeded, but its response was lost. Check the saved account status before making another request. The setup link cannot be recovered; a reviewed reissue invalidates any previous link.' : err.message);
      resource.reload();
    } finally { setBusy(false); }
  }
  async function copyLink() {
    try { await navigator.clipboard.writeText(secret.url); setNotice('Private setup link copied. Share it only with this student.'); }
    catch { setError('Copying is unavailable. Reveal the private setup link and copy it from the read-only field.'); }
  }
  async function updateAccount(body, description) {
    if (busy || forbidden || !studentActive || (uncertain && !checked)) return;
    setBusy(true); setError(''); setNotice(''); setSecret(null); setRevealed(false); setChecked(false); setReissueReviewed(false);
    try {
      const result = await api.updateStudentLoginAccount(studentId, body);
      if (!result?.account || typeof result.account.username !== 'string') throw new TypeError('The saved account response could not be verified.');
      setUncertain(false); setEmailUncertain(false); setNotice(description); resource.reload();
    } catch (err) {
      const unknown = ![400, 403, 404, 409, 429].includes(err.status);
      setUncertain(unknown); if (err.status === 403) setForbidden(true);
      setError(unknown ? 'The account change may have succeeded. Check the saved account status before making another change. No change will be repeated automatically.' : err.message); resource.reload();
    } finally { setBusy(false); }
  }
  async function sendEmail(body) {
    if (busy || forbidden || !studentActive || ((emailUncertain || uncertain) && !checked)) return;
    setBusy(true); setError(''); setNotice(''); setSecret(null); setRevealed(false); setChecked(false); setReissueReviewed(false);
    try {
      const result = await api.emailStudentAccessLink(studentId, body);
      if (!['accepted', 'unknown'].includes(result?.delivery_status) || !['setup', 'reset'].includes(result?.kind) || typeof result.recipient !== 'string') throw new TypeError('The email submission response could not be verified.');
      setEmailUncertain(result.delivery_status === 'unknown');
      if (result.delivery_status === 'accepted') setNotice(`Submitted to email provider: ${result.recipient}. Ask the student to check their inbox; provider acceptance does not confirm delivery.`);
      else setError('Email acceptance could not be confirmed. Check the student’s inbox and account status before explicitly requesting another link. This email will not be resent automatically.');
      resource.reload();
    } catch (err) {
      const unconfigured = err.status === 503 && err.details?.code === 'student_email_not_configured';
      const unknown = !unconfigured && ![400, 403, 404, 409, 429].includes(err.status);
      setEmailUncertain(unknown); if (err.status === 403) setForbidden(true);
      setError(unconfigured ? 'Email delivery is not configured. No email was submitted. Configure department email before trying again.' : unknown ? 'The email request may have been accepted, but its response could not be verified. Check the student’s inbox and saved account status before another request. No email will be resent automatically.' : err.message); resource.reload();
    } finally { setBusy(false); }
  }
  return <article className="live-inset"><div className="live-row"><h3>Student login</h3><button type="button" disabled={busy} onClick={refresh}>Check student account status</button></div>
    <p>The student signs in with their matriculation or UTME number and chooses their password privately. Email access instructions contain a private setup or reset link, never a password.</p>
    {!studentActive && <p className="live-alert">This student record is inactive. Account setup is unavailable until its status is reviewed.</p>}
    <Alert>{error}</Alert>{notice && <p role="status" className="live-notice">{notice}</p>}
    <RemoteState resource={resource}>{(metadata) => {
      const { account } = metadata;
      const preferredUsername = metadata.preferred_username || identifierValue || '';
      return <>
      {account ? <dl className="live-details"><div><dt>Sign-in username</dt><dd>{account.username}</dd></div><div><dt>Recovery email</dt><dd>{account.email || 'Not supplied'}</dd></div><div><dt>Account status</dt><dd>{!account.is_active ? 'Inactive' : account.setup_pending ? 'Waiting for the student to set a password' : 'Ready to sign in'}</dd></div></dl> : <p>No sign-in account is linked to this student record.</p>}
      {forbidden ? <p>Account management is no longer available to this session. Refresh the portal to check your current access.</p> : !account ? <>
        {uncertain && checked && <button type="button" disabled={busy} onClick={() => { setUncertain(false); setError(''); }}>Begin a new account request after checking status</button>}
        <form className="live-form" onSubmit={(event) => issue(event, null)}>
          <label>Student sign-in username<input name="username" value={preferredUsername} readOnly autoComplete="off" required disabled={busy || uncertain || !studentActive} /></label>
          <label>Student recovery email (optional)<input name="email" type="email" autoComplete="off" disabled={busy || uncertain || !studentActive} /></label>
          <p className="live-hint">The username matches the current student identifier exactly, including slashes and leading zeros. Add the student’s own email for private setup and password recovery links.</p>
          <button className="live-primary" disabled={busy || uncertain || !studentActive || !preferredUsername}>{busy ? 'Creating…' : 'Create student sign-in and setup link'}</button>
        </form>
      </> : account.is_active && account.setup_pending ? <form className="live-form" onSubmit={(event) => issue(event, account)}>
        <label className="live-check"><input type="checkbox" checked={reissueReviewed} onChange={(event) => setReissueReviewed(event.target.checked)} disabled={busy || !studentActive || (uncertain && !checked)} />I understand that a new setup link invalidates all previous setup links for this account.</label>
        <button disabled={busy || !reissueReviewed || !studentActive || (uncertain && !checked)}>{busy ? 'Issuing…' : 'Reissue private setup link'}</button>
      </form> : account.is_active ? <p>This account already has a password. The student can <Link to="/login">sign in</Link> or use password recovery if needed.</p> : <p>This sign-in account is inactive. Review its activation before issuing any setup link.</p>}
      {account && !forbidden && <>
        <UsernameReview key={`username:${account.username}:${preferredUsername}`} account={account} preferredUsername={preferredUsername} identifierType={identifierType} disabled={busy || !studentActive || !account.is_active || (uncertain && !checked)} onSave={updateAccount} />
        <StudentEmailEditor key={`email:${account.email}`} account={account} disabled={busy || !studentActive || !account.is_active || (uncertain && !checked)} onSave={updateAccount} />
        <EmailAccessLink key={`send:${account.username}:${account.email}:${account.setup_pending}`} account={account} available={metadata.email_delivery_available} disabled={busy || !studentActive || ((emailUncertain || uncertain) && !checked)} uncertain={emailUncertain} onSend={sendEmail} />
      </>}
      {secret && (!account || account.setup_pending) && !forbidden && <div className="live-notice"><h4>Private student setup link</h4><p>Single use; valid for up to {Math.ceil(secret.expiresIn / 60)} minutes from issue. Share only with this student. No email was sent.</p>
        <div className="live-downloads"><button type="button" onClick={() => setRevealed((value) => !value)}>{revealed ? 'Hide private setup link' : 'Reveal private setup link'}</button><button type="button" onClick={copyLink}>Copy private setup link</button></div>
        {revealed && <><label>Password setup link<input readOnly value={secret.url} autoComplete="off" spellCheck="false" /></label><a href={secret.url} target="_blank" rel="noreferrer">Open student password setup</a></>}
        <p className="live-hint">The link is kept only in this open record and disappears when you leave or refresh it.</p>
      </div>}
      <p className="live-hint">Keep the app running. A localhost or 127.0.0.1 setup or reset link works only on this laptop; another device needs a reachable application address.</p>
    </>; }}</RemoteState>
  </article>;
}

function UsernameReview({ account, preferredUsername, identifierType, disabled, onSave }) {
  const [reviewed, setReviewed] = useState(false);
  const label = identifierType === 'utme' ? 'UTME number' : 'matric number';
  if (!preferredUsername || account.username === preferredUsername) return <p className="live-hint">The sign-in username matches the current student identifier.</p>;
  return <details><summary>Change existing username to {label}</summary><p>Current username: <strong>{account.username}</strong><br />New username: <strong>{preferredUsername}</strong></p>
    <p>The old username will stop working. An existing password and the student’s linked records stay in place.</p>{account.setup_pending && <p className="live-hint">This change invalidates previous setup links. Issue a new link afterward.</p>}
    <form className="live-form" onSubmit={(event) => { event.preventDefault(); if (reviewed) onSave({ expected_username: account.username, expected_email: account.email || '', use_student_identifier: true, expected_identifier_value: preferredUsername }, 'Sign-in username updated to the current student identifier.'); }}>
      <label className="live-check"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} disabled={disabled} />I reviewed the current and new student usernames.</label>
      <button disabled={disabled || !reviewed}>Use {label}</button>
    </form>
  </details>;
}

function StudentEmailEditor({ account, disabled, onSave }) {
  return <details open={!account.email}><summary>{account.email ? 'Update student email' : 'Add student email'}</summary><p>Use the student’s own address and review it before sending an access link.</p>
    {account.setup_pending && <p className="live-hint">Changing this address invalidates previous setup links; issue a new link afterward.</p>}
    <form className="live-form" onSubmit={(event) => { event.preventDefault(); onSave({ expected_username: account.username, expected_email: account.email || '', email: new FormData(event.currentTarget).get('email').trim() }, 'Student email updated. Review the recipient before sending an access link.'); }}>
      <label>Student recovery email<input name="email" type="email" defaultValue={account.email || ''} autoComplete="off" disabled={disabled} /></label><button disabled={disabled}>Save student email</button>
    </form>
  </details>;
}

function EmailAccessLink({ account, available, disabled, uncertain, onSend }) {
  const [reviewed, setReviewed] = useState(false);
  const eligible = available && account.is_active && !!account.email;
  return <div className="live-inset"><h4>Email student access link</h4>
    {!available && <p>Email delivery is not configured. Configure department email before sending an access link.</p>}
    {!account.email && <p>Add the student’s email above before sending an access link.</p>}
    {account.setup_pending ? <p>A private password setup link will be submitted. It invalidates all previous setup links for this account.</p> : <p>A private password reset link will be submitted. The existing password stays valid until the student completes the reset.</p>}
    {uncertain && <p className="live-alert">Check the student’s inbox, then use Check student account status before requesting another email.</p>}
    <form className="live-form" onSubmit={(event) => { event.preventDefault(); if (reviewed && eligible && !disabled) { setReviewed(false); onSend({ expected_username: account.username, expected_email: account.email, confirm_reissue: true }); } }}>
      <label className="live-check"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} disabled={disabled || !eligible} />I reviewed the recipient address {account.email || '(not supplied)'} and confirm sending this private access link.</label>
      <button disabled={disabled || !eligible || !reviewed}>{account.setup_pending ? 'Email private setup link' : 'Email private reset link'}</button>
    </form>
  </div>;
}
