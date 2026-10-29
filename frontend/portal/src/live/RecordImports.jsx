import { useRef, useState } from 'react';
import SourceComparisons from './SourceComparisons';
import { Link } from 'react-router-dom';
import * as api from '../api';
import { Alert, Empty, Pager, RemoteState, Table } from './ui';
import { formatDate, hasPermission, isHod, useRemote } from './resources';

const resultTemplate = 'identifier_type,identifier_value,course_code,academic_session,semester,attempt_number,score\r\nmatriculation,SYNTHETIC/001,EEE101,2026/2027,harmattan,1,68.00\r\n';
const actionLabels = { create_result: 'New result', unchanged: 'Already recorded', correction: 'Score correction', blocked: 'Needs resolution' };
const waitingForRegistration = (row) => row.action === 'blocked' && row.code === 'unknown_student';

function Summary({ value }) {
  return <dl className="live-import-summary">{[['total', 'Rows'], ['new_results', 'New results'], ['unchanged', 'Already recorded'], ['corrections', 'Score corrections'], ['blocked', 'On hold / needs review']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{value[key] || 0}</dd></div>)}</dl>;
}

function Receipt({ value, recovered }) {
  return <div className="live-notice" role="status"><h3>{recovered ? 'Saved receipt recovered' : 'Import completed'}</h3><p>Receipt: <strong>{value.import_id}</strong></p>
    <p>{value.created_results || 0} results added · {value.updated_results || 0} results corrected · {value.unchanged || 0} entries already recorded.</p>
    <p>Saved {formatDate(value.committed_at)}. New and corrected scores require separate result verification.</p></div>;
}

export default function RecordImports({ user }) {
  const canRegister = hasPermission(user, 'students.view_student') && hasPermission(user, 'students.add_student');
  const canResults = hasPermission(user, 'students.view_student') && hasPermission(user, 'academics.view_result') && hasPermission(user, 'academics.add_result');
  const allowed = canResults && (isHod(user) || !!user.adviser_levels?.length);
  const [file, setFile] = useState(null), [requestId, setRequestId] = useState('');
  const [batch, setBatch] = useState(null), [approvals, setApprovals] = useState({});
  const [prepared, setPrepared] = useState(null);
  const [context, setContext] = useState({ attempt_number: '', academic_session: '', semester: '', include_reviewed_zero_scores: false, strategy: 'lines' });
  const [contextExpanded, setContextExpanded] = useState(false);
  const [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [recovered, setRecovered] = useState(false);
  const [page, setPage] = useState(1), [historyRevision, setHistoryRevision] = useState(0);
  const sequence = useRef(0);
  const history = useRemote((signal) => allowed ? api.listRecordImports(page, signal, 'results') : Promise.resolve({ results: [], count: 0 }), [allowed, page, historyRevision]);
  if (!allowed) return <section className="live-card"><h2>Import access unavailable</h2><p>An active adviser assignment and permission to view students and add results are required.</p></section>;
  function resetPreview() { setBatch(null); setPrepared(null); setApprovals({}); setReviewed(false); setError(''); setNotice(''); setRecovered(false); setUncertain(false); setStale(false); }
  function chooseFile(event) {
    sequence.current += 1; const chosen = event.target.files?.[0] || null;
    setFile(chosen); setRequestId(chosen ? crypto.randomUUID() : ''); resetPreview();
  }
  function changeContext(name, value) {
    sequence.current += 1; setContext((old) => ({ ...old, [name]: value })); setRequestId(file ? crypto.randomUUID() : ''); resetPreview();
  }
  async function requestPreview(csvText, filename, started, sourceContext) {
    const data = await api.previewRecordImport({ kind: 'results', request_id: requestId, filename, csv_text: csvText, ...(sourceContext ? { source_context: sourceContext } : {}) });
    if (started !== sequence.current) return;
    setBatch(data); setStale(false); setHistoryRevision((value) => value + 1);
  }
  async function preview(event) {
    event.preventDefault(); if (!file || busy) return;
    const extension = file.name.toLowerCase().split('.').pop();
    if (!['csv', 'pdf'].includes(extension)) { setError('Choose a CSV or PDF mark sheet. Export Excel workbooks as CSV UTF-8 first.'); return; }
    if (file.size > 2 * 1024 * 1024) { setError('Choose a source file no larger than 2 MiB.'); return; }
    const started = ++sequence.current; setBusy(true); setError(''); setNotice(''); setBatch(null); setPrepared(null); setApprovals({}); setReviewed(false); setRecovered(false);
    try {
      if (extension === 'csv') new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer());
      const source = await api.prepareRecordImport(file, context);
      if (started !== sequence.current) return;
      if (source.format !== 'canonical_csv') setPrepared(source);
      if (source.summary.accepted_rows) await requestPreview(source.csv_text, source.filename, started, source.source_context);
    } catch (err) {
      if (started === sequence.current) {
        if (err.status === 400) setContextExpanded(true);
        const help = err.status === 0 || err.status >= 500 ? 'You may request this same preview again; its request ID is retained.' : 'Check the reviewed attempt number. Supply session and semester only if the sheet does not provide them.';
        setError(err instanceof TypeError ? 'The file could not be read as UTF-8 CSV. Export it as CSV UTF-8 and try again.' : `${err.message} ${help}`);
      }
    } finally { if (started === sequence.current) setBusy(false); }
  }
  async function loadBatch(id, refresh = false) {
    const started = ++sequence.current; setBusy(true); setError(''); setNotice('');
    try {
      const data = refresh ? await api.refreshRecordImport(id) : await api.getRecordImport(id);
      if (started !== sequence.current) return;
      if (data.kind !== 'results') { setError('This workspace opens result uploads only. Student registration is managed separately under Students.'); return; }
      setBatch(data); setFile(null); setPrepared(null); setRequestId(''); setApprovals({}); setReviewed(false); setUncertain(false); setStale(false); setRecovered(!!data.receipt);
      if (refresh) setNotice('Preview refreshed. Review all rows and corrections again before importing.');
      setHistoryRevision((value) => value + 1);
    } catch (err) { if (started === sequence.current) setError(err.message); }
    finally { if (started === sequence.current) setBusy(false); }
  }
  function approve(rowNumber, changes) { setApprovals((old) => ({ ...old, [rowNumber]: { ...old[rowNumber], ...changes } })); setReviewed(false); }
  const corrections = batch?.rows.filter((row) => row.action === 'correction') || [];
  const correctionsReady = corrections.every((row) => approvals[row.row_number]?.checked && approvals[row.row_number]?.reason?.trim());
  const canCommit = !!batch?.can_commit && !batch?.receipt && !batch?.summary.blocked && reviewed && correctionsReady && !busy && !uncertain && !stale;
  async function commit(event) {
    event.preventDefault(); if (!canCommit) return;
    setBusy(true); setError(''); setNotice(''); setRecovered(false);
    try {
      const data = await api.commitRecordImport(batch.id, {
        preview_digest: batch.preview_digest,
        correction_approvals: corrections.map((row) => ({ row_number: row.row_number, reason: approvals[row.row_number].reason.trim() })),
      });
      setBatch(data); setHistoryRevision((value) => value + 1);
    } catch (err) {
      if (err.status === 0 || err.status >= 500) { setUncertain(true); setError('The import outcome is uncertain. Check the saved receipt before trying another import.'); }
      else { setReviewed(false); setStale(err.status === 409); setError(`${err.message} Refresh this preview and review its current rows before continuing.`); }
    } finally { setBusy(false); }
  }
  return <>
    <section className="live-card live-upload-card"><h2>Upload master mark-sheet results</h2><p>Upload the department’s PDF to prepare a CSV and match its course, session, semester and score fields.</p>
      <Alert>{error}</Alert>{notice && <p className="live-notice" role="status">{notice}</p>}
      <div className="live-upload-layout"><form className="live-form" onSubmit={preview}>
        <label>Master mark sheet (PDF or CSV)<input type="file" accept=".pdf,.csv,application/pdf,text/csv" onChange={chooseFile} disabled={busy || uncertain} /></label>
        <label>Attempt number for converted rows<input type="number" min="1" max="32767" value={context.attempt_number} disabled={busy || uncertain} onChange={(event) => changeContext('attempt_number', event.target.value)} placeholder="Enter the reviewed attempt, e.g. 1" /></label>
        <p className="live-hint">The sheet provides session and semester where available. Enter the attempt within that course offering; it is not guessed or increased to bypass duplicates. A results CSV already supplies each row’s attempt.</p>
        <details open={contextExpanded} onToggle={(event) => setContextExpanded(event.currentTarget.open)}><summary>Missing source context or extraction options</summary><p className="live-hint">Leave session and semester empty when they appear in the PDF or converter student CSV. Raw table CSV needs both from the original heading. Supplied values must agree with the sheet.</p>
          <label>Academic session for source context<input value={context.academic_session} disabled={busy || uncertain} onChange={(event) => changeContext('academic_session', event.target.value)} placeholder="2026/2027" pattern="[0-9]{4}/[0-9]{4}" /></label>
          <label>Semester for source context<select value={context.semester} disabled={busy || uncertain} onChange={(event) => changeContext('semester', event.target.value)}><option value="">Use source context where available</option><option value="harmattan">Harmattan</option><option value="rain">Rain</option></select></label>
          <label>PDF table extraction<select value={context.strategy} disabled={busy || uncertain} onChange={(event) => changeContext('strategy', event.target.value)}><option value="lines">Ruled tables</option><option value="text">Text-aligned tables</option></select></label>
        </details>
        <label className="live-check"><input type="checkbox" checked={context.include_reviewed_zero_scores} disabled={busy || uncertain} onChange={(event) => changeContext('include_reviewed_zero_scores', event.target.checked)} />I checked the source and confirm its recorded zero marks are actual zero scores.</label>
        <button className="live-primary" disabled={!file || busy || uncertain}>{busy ? 'Working…' : 'Convert and preview scores'}</button>
      </form>
      <aside className="live-upload-guide" aria-label="How result uploads work"><h3>A clear path to saved results</h3><ol><li><span className="live-upload-step" aria-hidden="true">1</span><div><strong>Choose the sheet</strong>Use the master-sheet PDF or an existing result CSV.</div></li><li><span className="live-upload-step" aria-hidden="true">2</span><div><strong>Review matched scores</strong>Check extracted marks, student matches and any corrections.</div></li><li><span className="live-upload-step" aria-hidden="true">3</span><div><strong>Save approved results</strong>Confirm your review before the records change.</div></li></ol>
      <details><summary>CSV files and format limits</summary><p>Existing converter *_students.csv and *_tables.csv files, or the result CSV template, can be used directly. Keep matriculation numbers as text. Up to 1000 course rows and 2 MiB per source; supported text PDFs have up to 20 pages. Scanned or different layouts require a reviewed conversion.</p><a href={`data:text/csv;charset=utf-8,${encodeURIComponent(resultTemplate)}`} download="results-synthetic-template.csv">Download results CSV template (synthetic example)</a></details>
      <p className="live-hint">Unregistered students remain on hold until registered separately under Students. Student registration and guardian sharing have their own workspaces.</p></aside></div>
    </section>
    {prepared && <section className="live-card"><h2>Converted score sheet</h2><p><strong>{file?.name}</strong> has been converted to <strong>{prepared.filename}</strong>. Review the conversion and scores below before saving.</p>
      <dl className="live-import-summary"><div><dt>Source course rows</dt><dd>{prepared.summary.source_course_rows}</dd></div><div><dt>Ready for matching</dt><dd>{prepared.summary.accepted_rows}</dd></div><div><dt>Need resolution</dt><dd>{prepared.summary.unresolved_rows}</dd></div></dl>
      {!!prepared.summary.unresolved_rows && <p className="live-alert">The converted CSV contains only the ready rows. Undecided NG or unreadable marks are held for review, and recorded zeros need source confirmation above. Nothing missing is replaced with zero. Review the excluded entries before saving any ready scores.</p>}
      {!prepared.summary.accepted_rows && <p className="live-alert">No scores are ready for database matching. Resolve the entries below, then convert the source again.</p>}
      <div className="live-downloads"><a download={prepared.filename} href={`data:text/csv;charset=utf-8,${encodeURIComponent(prepared.csv_text)}`}>Download prepared results CSV</a><a download="conversion-report.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify({ format: prepared.format, source_filename: file?.name, prepared_filename: prepared.filename, source_sha256: prepared.source_sha256, summary: prepared.summary, reviewed_context: prepared.reviewed_context || {}, complete_history: prepared.complete_history ?? false }, null, 2))}`}>Download conversion report</a><a download="extraction-issues.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(prepared.issues, null, 2))}`}>Download issue report</a><a download="extraction-trace.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(prepared.trace, null, 2))}`}>Download source trace</a></div>
      <p className="live-hint">Keep the original PDF or converter file and these reports privately with the department’s source records. The saved import retains the prepared CSV and supplied source context, including reported averages and extraction fields; keep the original file and separate conversion reports privately.</p>
      <details><summary>Prepared CSV rows</summary><pre className="live-source-preview">{prepared.csv_text}</pre></details>
      {!!prepared.issues.length && <Table headings={['Source', 'Student / course', 'Original mark', 'Issue']}>
        {prepared.issues.map((issue, index) => <tr key={index}><td>Record {issue.source_record ?? '—'} · Page {issue.source_page ?? '—'} · Table {issue.source_table ?? '—'}</td><td>{issue.identifier_value || 'Unresolved identifier'}<br />{issue.course_code || 'Unresolved course'}</td><td>{issue.raw_result ?? 'Not recorded'}</td><td>{issue.message || issue.code}</td></tr>)}
      </Table>}
      <details><summary>Source reference</summary><p className="live-hint">SHA-256: {prepared.source_sha256}</p></details>
    </section>}
    {batch && <section className="live-card"><div className="live-row"><h2>{batch.receipt ? 'Saved import' : 'Review import'}</h2><button disabled={busy} onClick={() => loadBatch(batch.id, !batch.receipt && !uncertain)}>{uncertain ? 'Check saved receipt' : batch.receipt ? 'Reload saved receipt' : 'Refresh preview after changes'}</button></div>
      <p><strong>{batch.filename}</strong> · Result upload · Preview revision {batch.revision}</p>
      <details><summary>Import reference</summary><p className="live-hint">{batch.id}<br />File SHA-256: {batch.file_sha256}</p></details>
      <SourceComparisons reports={batch.source_performance} importing />
      {batch.receipt ? <Receipt value={batch.receipt} recovered={recovered} /> : <><Summary value={batch.summary} />
        {!!batch.summary.blocked && <p className="live-alert">This upload is on hold until the flagged rows are resolved. Register missing students separately under Students, then reopen this upload from history and refresh its preview. No results from this batch are saved while a row is blocked.</p>}
        {uncertain && <p className="live-alert">Keep this import reference. The saved receipt records whether the transaction completed. Do not upload another copy to recover an uncertain outcome.</p>}
        <Table headings={['Source row', 'Student', 'Course / period', 'Action', 'Review']}>
          {batch.rows.map((row) => <tr key={row.row_number}><td>{row.row_number}</td><td>{row.full_name && <strong>{row.full_name}<br /></strong>}{row.identifier_value}<small className="live-hint">{row.identifier_type === 'utme' ? 'UTME' : 'Matriculation'}</small></td>
            <td>{row.course_code || 'Not supplied'}{row.academic_session && <><br />{row.academic_session} · {row.semester}<br />Attempt {row.attempt_number} · Score {row.score}</>}</td>
            <td>{waitingForRegistration(row) ? 'Awaiting student registration' : actionLabels[row.action] || row.action}</td><td>{row.message && <p>{row.message}</p>}
              {row.action === 'correction' && <div><p>Recorded score: {row.existing_score ?? 'Not scored'} → proposed score: {row.score}</p>
                {hasPermission(user, 'academics.change_result') ? <><label className="live-check"><input type="checkbox" checked={!!approvals[row.row_number]?.checked} disabled={busy || uncertain} onChange={(event) => approve(row.row_number, { checked: event.target.checked })} />Approve correction on row {row.row_number}</label><label>Correction reason for row {row.row_number}<input value={approvals[row.row_number]?.reason || ''} maxLength="1000" disabled={busy || uncertain} onChange={(event) => approve(row.row_number, { reason: event.target.value })} /></label></> : <p>A staff member with result correction permission must review this row.</p>}</div>}
              {row.action === 'blocked' && canRegister && (row.student_id || ['unknown_student', 'unavailable_student'].includes(row.code)) && <Link to={`/portal/${user.role}/students?${row.student_id ? `student=${encodeURIComponent(row.student_id)}` : `register=${encodeURIComponent(row.identifier_value)}&identifier_type=${encodeURIComponent(row.identifier_type)}`}`}>{row.student_id ? 'Review student record separately' : 'Register or check student separately'}</Link>}
            </td></tr>)}
        </Table>
        <form className="live-form live-wide" onSubmit={commit}><label className="live-check"><input type="checkbox" checked={reviewed} disabled={busy || uncertain || stale || !!batch.summary.blocked} onChange={(event) => setReviewed(event.target.checked)} />I reviewed the scores, excluded entries and any corrections against the original mark sheet.</label>
          <button className="live-primary" disabled={!canCommit}>{busy ? 'Saving…' : 'Commit reviewed import'}</button></form>
      </>}
    </section>}
    <section className="live-card"><div className="live-row"><h2>Your result upload history</h2><button disabled={busy} onClick={() => history.reload()}>Refresh import history</button></div><p>Resume a held upload after registering a missing student separately, or recover its receipt after a connection interruption.</p>
      <RemoteState resource={history}>{(data) => <>{!data.results.length ? <Empty>No results have been previewed by this account.</Empty> : <Table headings={['File', 'Status', 'Open']}>
        {data.results.map((row) => <tr key={row.id}><td>{row.filename}</td><td>{row.status}</td><td><button disabled={busy || uncertain} onClick={() => loadBatch(row.id)}>Open import {row.filename}</button></td></tr>)}</Table>}<Pager page={page} data={data} onChange={setPage} disabled={busy} /></>}</RemoteState>
    </section>
  </>;
}
