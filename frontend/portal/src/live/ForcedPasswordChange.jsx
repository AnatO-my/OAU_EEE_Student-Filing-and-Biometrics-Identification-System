import { useState } from 'react';
import { apiRequest } from '../api';
import { useAuth } from '../auth/useAuth';
export default function ForcedPasswordChange() {
  const { refreshUser } = useAuth();
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function submit(event) {
    event.preventDefault(); const form=new FormData(event.currentTarget);
    if(form.get('new_password')!==form.get('confirm')) { setError('The new passwords do not match.'); return; }
    setBusy(true); setError('');
    try { await apiRequest('/api/auth/password/change/',{method:'POST',body:{current_password:form.get('current_password'),new_password:form.get('new_password')}}); await refreshUser(); }
    catch(err) {setError(err.message);} finally {setBusy(false);}
  }
  return <main className="live-portal"><h1>Choose your password</h1><p>Change the temporary password before using your account.</p>
    <form className="live-form" onSubmit={submit}><label>Temporary password<input name="current_password" type="password" autoComplete="current-password" required /></label><label>New password<input name="new_password" type="password" autoComplete="new-password" required minLength={8}/></label><label>Confirm new password<input name="confirm" type="password" autoComplete="new-password" required/></label><button disabled={busy}>Save password and activate access</button></form>{error&&<p role="alert">{error}</p>}</main>;
}
