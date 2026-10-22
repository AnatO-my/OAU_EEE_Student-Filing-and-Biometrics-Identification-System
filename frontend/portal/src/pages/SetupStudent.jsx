import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { confirmStudentSetup } from '../api';
import { Alert } from '../live/ui';
import '../live/live.css';
import './SetupStudent.css';
import PasswordLinkSession from './PasswordLinkSession';

export default function SetupStudent() {
  return <PasswordLinkSession>{(credentials, consumed) => <SetupStudentForm initialCredentials={credentials} onConsumed={consumed} />}</PasswordLinkSession>;
}

function SetupStudentForm({ initialCredentials, onConsumed }) {
  const [credentials, setCredentials] = useState(initialCredentials);
  const [busy, setBusy] = useState(false), [complete, setComplete] = useState(null), [error, setError] = useState(''), [uncertain, setUncertain] = useState(false);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, []);
  async function submit(event) {
    event.preventDefault(); if (busy || uncertain) return;
    const form = event.currentTarget, values = new FormData(form);
    if (values.get('password') !== values.get('confirm')) { setError('The passwords do not match.'); return; }
    const started = ++generation.current; setBusy(true); setError('');
    try {
      const result = await confirmStudentSetup(credentials.uid, credentials.token, values.get('password'));
      if (started !== generation.current) return;
      if (typeof result?.username !== 'string' || !result.username) throw new TypeError('The password setup response could not be verified.');
      form.reset(); setComplete(result); setCredentials({ uid: null, token: null }); onConsumed();
    } catch (err) {
      if (started !== generation.current) return;
      if (![400, 403, 429].includes(err.status)) {
        // A malformed success body or a changed session may follow a completed
        // write too. Only an explicit validation/throttle rejection is safe to
        // correct and submit again without checking the saved account.
        setUncertain(true); form.reset(); setCredentials({ uid: null, token: null }); onConsumed();
        setError('The response was interrupted, so your password may already have been set. Try signing in, or ask the department to check your account. This request will not be sent again.');
      } else setError(err.message);
    } finally { if (started === generation.current) setBusy(false); }
  }
  return <main className="live-session student-password-setup"><section className="live-card"><p className="live-kicker">EEE OAU · Student access</p><h1>Set your student password</h1>
    {complete ? <><p role="status">Your password has been set. Sign in with username <strong>{complete.username}</strong> and your new password.</p><Link to="/login">Sign in</Link></> : uncertain ? <><Alert>{error}</Alert><Link to="/login">Try signing in</Link></> : !credentials.uid || !credentials.token ? <><Alert>This setup link is incomplete. Ask the HOD for a new private setup link.</Alert><Link to="/login">Return to sign in</Link></> : <>
      <p>Choose a password privately. This single-use link connects you to the student account prepared by the department.</p><Alert>{error}</Alert>
      <form className="live-form" onSubmit={submit}><label>New student password<input name="password" type="password" autoComplete="new-password" required disabled={busy} /></label><label>Confirm student password<input name="confirm" type="password" autoComplete="new-password" required disabled={busy} /></label><button className="live-primary" disabled={busy}>{busy ? 'Setting password…' : 'Set student password'}</button></form>
      <p className="live-hint">An expired or already-used link cannot be reused. Ask the HOD for a new link if setup is still pending. Your password is not sent to the HOD.</p>
    </>}
  </section></main>;
}
