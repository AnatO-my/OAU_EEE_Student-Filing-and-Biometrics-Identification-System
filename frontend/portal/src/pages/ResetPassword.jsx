import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { confirmPasswordReset } from '../api';
import { Alert } from '../live/ui';
import PasswordLinkSession from './PasswordLinkSession';
import '../live/live.css';
import './SetupStudent.css';

export default function ResetPassword() {
  return <PasswordLinkSession allowQuery>{(credentials, consumed) => <ResetForm initialCredentials={credentials} onConsumed={consumed} />}</PasswordLinkSession>;
}

function ResetForm({ initialCredentials, onConsumed }) {
  const [credentials, setCredentials] = useState(initialCredentials);
  const [busy, setBusy] = useState(false), [complete, setComplete] = useState(false), [error, setError] = useState(''), [uncertain, setUncertain] = useState(false);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, []);
  async function submit(event) {
    event.preventDefault(); if (busy || uncertain) return;
    const form = event.currentTarget, values = new FormData(form);
    if (values.get('password') !== values.get('confirm')) { setError('The passwords do not match.'); return; }
    const started = ++generation.current; setBusy(true); setError('');
    try {
      const result = await confirmPasswordReset(credentials.uid, credentials.token, values.get('password'));
      if (started !== generation.current) return;
      if (typeof result?.detail !== 'string') throw new TypeError('The reset response could not be verified.');
      form.reset(); setComplete(true); setCredentials({ uid: null, token: null }); onConsumed();
    } catch (err) {
      if (started !== generation.current) return;
      if (![400, 403, 429].includes(err.status)) {
        form.reset(); setCredentials({ uid: null, token: null }); onConsumed(); setUncertain(true);
        setError('The response was interrupted, so your password may already have changed. Try signing in, or ask the department to check your account. This request will not be sent again.');
      } else setError(err.message);
    } finally { if (started === generation.current) setBusy(false); }
  }
  return <main className="live-session student-password-setup"><section className="live-card"><h1>Choose a new password</h1>
    {complete ? <><p role="status">Your password has been reset.</p><Link to="/login">Sign in</Link></> : uncertain ? <><Alert>{error}</Alert><Link to="/login">Try signing in</Link></> : !credentials.uid || !credentials.token ? <><Alert>This reset link is incomplete. Request a new link.</Alert><Link to="/recover-password">Request a reset link</Link></> : <>
      <p>Choose your password privately. No password is sent by email.</p><Alert>{error}</Alert><form className="live-form" onSubmit={submit}><label>New password<input name="password" type="password" autoComplete="new-password" required disabled={busy} /></label>
        <label>Confirm new password<input name="confirm" type="password" autoComplete="new-password" required disabled={busy} /></label><button disabled={busy} className="live-primary">{busy ? 'Resetting…' : 'Reset password'}</button></form>
      <Link to="/recover-password">Request a new reset link</Link></>}</section></main>;
}
