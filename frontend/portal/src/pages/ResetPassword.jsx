import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { confirmPasswordReset } from '../api';

export default function ResetPassword() {
  const [query, setQuery] = useSearchParams();
  const [credentials] = useState(() => ({ uid: query.get('uid'), token: query.get('token') }));
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [state, setState] = useState({ busy: false, error: '', complete: false });
  const validLink = !!credentials.uid && !!credentials.token;
  async function submit(event) {
    event.preventDefault();
    if (state.busy) return;
    if (password !== confirmation) { setState({ busy: false, error: 'The passwords do not match.', complete: false }); return; }
    setState({ busy: true, error: '', complete: false });
    try {
      await confirmPasswordReset(credentials.uid, credentials.token, password);
      setPassword(''); setConfirmation('');
      setQuery({}, { replace: true });
      setState({ busy: false, error: '', complete: true });
    } catch (error) {
      setState({ busy: false, error: error.message || 'Unable to reset your password.', complete: false });
    }
  }
  return <main className="live-portal"><section className="live-card"><h1>Set a new password</h1>
    {state.complete ? <><p role="status">Password reset. Sign in with your new password.</p><Link to="/login">Sign in</Link></> :
      !validLink ? <><p role="alert">This reset link is incomplete. Request a new link.</p><Link to="/recover-password">Request reset link</Link></> :
        <form onSubmit={submit}><p>Choose a new password for your departmental account.</p>
          {state.error && <p role="alert">{state.error}</p>}
          <label>New password<input type="password" autoComplete="new-password" required value={password} onChange={e => setPassword(e.target.value)} disabled={state.busy} /></label>
          <label>Confirm new password<input type="password" autoComplete="new-password" required value={confirmation} onChange={e => setConfirmation(e.target.value)} disabled={state.busy} /></label>
          <button disabled={state.busy}>{state.busy ? 'Saving…' : 'Set new password'}</button>
        </form>}
  </section></main>;
}
