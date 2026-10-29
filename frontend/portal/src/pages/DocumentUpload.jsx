import { useState } from 'react';
import { uploadStudentDocument } from '../api';

export default function DocumentUpload({ studentId }) {
  const [file, setFile] = useState(null);
  const [type, setType] = useState('result');
  const [confirmed, setConfirmed] = useState(false);
  const [state, setState] = useState({ busy: false, error: '', document: null });
  async function submit(event) {
    event.preventDefault();
    if (!file || !confirmed || state.busy) return;
    setState({ busy: true, error: '', document: null });
    try { setState({ busy: false, error: '', document: await uploadStudentDocument(studentId, file, type) }); setConfirmed(false); }
    catch (error) {
      setConfirmed(false);
      const uncertain = !error.status || error.status < 400 || error.status >= 500;
      setState({ busy: false, error: uncertain ? 'The upload outcome is unconfirmed. Check with the administrator before uploading again.' : error.message, document: null });
    }
  }
  return <section className="live-card"><h2>Upload student document</h2><p>PDF, JPEG and PNG scans are checked by the server. First uploads become active. A student replacement awaits part-adviser or HOD approval; the previous version stays active.</p>
    <form className="live-form" onSubmit={submit}><label>Document type<select value={type} disabled={state.busy} onChange={event => { setType(event.target.value); setConfirmed(false); }}><option value="clearance">Clearance certificate</option><option value="jamb">JAMB result</option><option value="waec">WAEC result</option><option value="state_origin">State of origin certificate</option><option value="result">Result</option><option value="biodata">Biodata</option><option value="birth_cecrtificate">Birth certificate</option><option value="other">Other</option></select></label>
      <label>Scanned document<input type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={state.busy} onChange={event => { setFile(event.target.files?.[0] || null); setConfirmed(false); }} /></label>
      <label><span><input type="checkbox" checked={confirmed} disabled={state.busy} onChange={event => setConfirmed(event.target.checked)} /> I have checked the student, document type and replacement.</span></label><button disabled={state.busy || !confirmed || !file}>{state.busy ? 'Uploading…' : 'Upload document'}</button></form>
    {state.error && <p role="alert">{state.error}</p>}
    {state.document && <p role="status">{state.document.original_filename}: {state.document.approval_state === 'pending' ? 'Pending staff approval' : state.document.status === 'accepted' ? 'Accepted' : 'Needs review'}. {state.document.quality_notes}</p>}
  </section>;
}
