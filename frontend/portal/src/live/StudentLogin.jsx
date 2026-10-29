import { useState } from 'react';
import { apiRequest } from '../api';
export default function StudentLogin({user,studentId,studentActive=true}) {
 const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
 if(!user?.is_staff)return null;
 async function issue(event) {
  event.preventDefault();setBusy(true);setMessage('');
  try {const result=await apiRequest(`/api/workflows/students/${studentId}/`,{method:'POST',body:{action:'temporary_password',email:new FormData(event.currentTarget).get('email')}});setMessage(result.delivery_status==='accepted'?'Temporary password submitted by email. The student must change it before accessing records.':'Email acceptance could not be confirmed. Check the student inbox before explicitly reissuing; a reissue invalidates the earlier temporary password.');}
  catch(err){setMessage(err.message);}finally{setBusy(false);}
 }
 return <section className="live-inset"><h3>Student login</h3><p>Pre-register the student, then email a temporary password. Existing established accounts use the single-use password reset link.</p><form className="live-form" onSubmit={issue}><label>Student email<input type="email" name="email" required/></label><button disabled={busy||!studentActive}>Email temporary password</button></form>{message&&<p role="status">{message}</p>}</section>;
}
