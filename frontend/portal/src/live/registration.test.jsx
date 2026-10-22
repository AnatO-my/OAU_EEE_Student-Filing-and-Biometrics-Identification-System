import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StudentRegistration, { PromoteIdentifier, StudentProfileEditor } from './StudentRegistration';
import RecordImports from './RecordImports';
import * as api from '../api';

vi.mock('../api', async (original) => ({ ...await original(), lookupStudentIdentifier: vi.fn(), createStudent: vi.fn(), updateStudent: vi.fn(), promoteStudentIdentifier: vi.fn(), listRecordImports: vi.fn(), prepareRecordImport: vi.fn(), previewRecordImport: vi.fn(), getRecordImport: vi.fn(), refreshRecordImport: vi.fn(), commitRecordImport: vi.fn() }));
const adviser = { id: 2, role: 'staff', is_staff: true, adviser_levels: [300], permissions: ['students.view_student', 'students.add_student', 'students.change_student', 'academics.view_result', 'academics.add_result', 'academics.change_result'] };
const hod = { id: 1, role: 'hod', is_staff: true, is_superuser: true, adviser_levels: [], permissions: [] };
const student = { student_id: 'student-uuid', identifier_type: 'utme', identifier_value: '000123', full_name: 'Synthetic Example', admission_year: 2024, current_level: 300, mode_of_admission: 'utme', phone_number: '' };
const batch = { id: 'import-uuid', request_id: 'request-uuid', kind: 'results', filename: 'results.csv', file_sha256: 'file-digest', preview_digest: 'review-digest', revision: 1, status: 'preview', can_commit: true, receipt: null, summary: { total: 3, new_students: 0, new_results: 1, unchanged: 1, corrections: 1, blocked: 0 }, rows: [
  { row_number: 2, identifier_type: 'matriculation', identifier_value: '001234', course_code: 'EEE301', academic_session: '2026/2027', semester: 'harmattan', attempt_number: 1, score: '70.00', action: 'create_result' },
  { row_number: 3, identifier_type: 'matriculation', identifier_value: '001234', course_code: 'EEE302', academic_session: '2026/2027', semester: 'harmattan', attempt_number: 1, score: '65.00', action: 'unchanged' },
  { row_number: 4, identifier_type: 'matriculation', identifier_value: '001234', course_code: 'EEE303', academic_session: '2026/2027', semester: 'harmattan', attempt_number: 1, score: '68.00', existing_score: '58.00', action: 'correction' },
] };
const committed = { ...batch, status: 'committed', can_commit: false, receipt: { import_id: 'import-uuid', committed_at: '2026-10-21T10:00:00Z', created_students: 0, created_results: 1, updated_results: 1, unchanged: 1 } };
const csv = 'identifier_type,identifier_value,course_code,academic_session,semester,attempt_number,score\r\nmatriculation,001234,EEE301,2026/2027,harmattan,1,70.00\r\n';
function file(name = 'results.csv', content = csv) { const value = new File([content], name); value.arrayBuffer = async () => new TextEncoder().encode(content).buffer; return value; }
function sourceInput() { return screen.getByLabelText('Master mark sheet (PDF or CSV)'); }
function imports(user = hod) { return render(<MemoryRouter><RecordImports user={user} /></MemoryRouter>); }
async function previewFile(value = file()) {
  fireEvent.change(sourceInput(), { target: { files: [value] } });
  fireEvent.click(screen.getByRole('button', { name: 'Convert and preview scores' }));
  await screen.findByRole('heading', { name: 'Review import' });
}
function approve() {
  fireEvent.click(screen.getByLabelText('Approve correction on row 4'));
  fireEvent.change(screen.getByLabelText('Correction reason for row 4'), { target: { value: 'Compared with the approved corrected sheet.' } });
  fireEvent.click(screen.getByLabelText('I reviewed the scores, excluded entries and any corrections against the original mark sheet.'));
}
beforeEach(() => { vi.clearAllMocks(); api.prepareRecordImport.mockImplementation(async (value) => ({ format: 'canonical_csv', csv_text: new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(await value.arrayBuffer()), filename: value.name, source_sha256: 'source-digest', summary: { source_course_rows: 1, accepted_rows: 1, unresolved_rows: 0 }, issues: [], trace: [] })); api.listRecordImports.mockResolvedValue({ results: [], count: 0, next: null }); api.previewRecordImport.mockResolvedValue(batch); api.commitRecordImport.mockResolvedValue(committed); });
afterEach(cleanup);

describe('adviser registration and profile completion', () => {
  it('hides registration when permission or current adviser assignment is missing', () => {
    const { rerender } = render(<StudentRegistration user={{ ...adviser, permissions: ['students.view_student'] }} />);
    expect(screen.queryByText('Register student')).toBeNull();
    rerender(<StudentRegistration user={{ ...adviser, adviser_levels: [] }} />);
    expect(screen.queryByText('Register student')).toBeNull();
  });
  it('checks the exact text identifier and registers only in an assigned level without creating an account', async () => {
    api.lookupStudentIdentifier.mockRejectedValue(new api.ApiError('Not found.', 404)); api.createStudent.mockResolvedValue(student);
    render(<StudentRegistration user={adviser} initialIdentifier="000123" />);
    fireEvent.click(screen.getByRole('button', { name: 'Check identifier' }));
    await screen.findByLabelText('Full name');
    expect([...screen.getByLabelText('Current level').options].map((option) => option.value)).toEqual(['300']);
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Synthetic Example' } });
    fireEvent.change(screen.getByLabelText('Admission year'), { target: { value: '2024' } });
    fireEvent.click(screen.getByRole('button', { name: 'Register approved student' }));
    await screen.findByText('Student registered. No login account was created.');
    expect(api.lookupStudentIdentifier).toHaveBeenCalledWith('matriculation', '000123');
    expect(api.createStudent).toHaveBeenCalledWith({ identifier_type: 'matriculation', identifier_value: '000123', full_name: 'Synthetic Example', surname: '', phone_number: '', admission_year: 2024, mode_of_admission: 'utme', current_level: 300 });
  });
  it('shows an existing record instead of another registration form', async () => {
    api.lookupStudentIdentifier.mockResolvedValue(student); render(<StudentRegistration user={adviser} initialIdentifier="000123" />);
    fireEvent.click(screen.getByText('Check identifier')); await screen.findByText('Existing student: Synthetic Example');
    expect(screen.queryByRole('button', { name: 'Register approved student' })).toBeNull(); expect(api.createStudent).not.toHaveBeenCalled();
  });
  it('invalidates a checked identifier and blocks blind retries after a conflicting save', async () => {
    api.lookupStudentIdentifier.mockRejectedValue(new api.ApiError('Not found.', 404)); api.createStudent.mockRejectedValue(new api.ApiError('Identifier unavailable.', 409));
    render(<StudentRegistration user={adviser} initialIdentifier="000123" />); fireEvent.click(screen.getByText('Check identifier'));
    await screen.findByLabelText('Full name'); fireEvent.change(screen.getByLabelText('Student identifier'), { target: { value: '000124' } });
    expect(screen.queryByRole('button', { name: 'Register approved student' })).toBeNull();
    fireEvent.click(screen.getByText('Check identifier')); await screen.findByLabelText('Full name');
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Synthetic Example' } }); fireEvent.change(screen.getByLabelText('Admission year'), { target: { value: '2024' } }); fireEvent.click(screen.getByText('Register approved student'));
    await screen.findByRole('alert'); expect(screen.queryByText('Register approved student')).toBeNull(); expect(api.createStudent).toHaveBeenCalledOnce();
  });
  it('does not read or overwrite the existing surname when completing optional details', async () => {
    api.updateStudent.mockResolvedValue(student); const onSaved = vi.fn(); render(<StudentProfileEditor row={student} user={adviser} onSaved={onSaved} />);
    expect(screen.getByLabelText('Set surname (leave blank to keep existing)').value).toBe('');
    fireEvent.submit(screen.getByRole('button', { name: 'Save student details' }).closest('form'));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(api.updateStudent).toHaveBeenCalledWith('student-uuid', { full_name: 'Synthetic Example', phone_number: '', admission_year: 2024, mode_of_admission: 'utme' });
  });
  it('shows UTME promotion only to the HOD and binds the expected old identifier', async () => {
    const { rerender } = render(<PromoteIdentifier row={student} user={adviser} />); expect(screen.queryByText('Assign matriculation number')).toBeNull();
    api.promoteStudentIdentifier.mockResolvedValue({}); rerender(<PromoteIdentifier row={student} user={hod} onSaved={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Assigned matriculation number'), { target: { value: 'EEE/2026/001' } });
    fireEvent.submit(screen.getByRole('button', { name: 'Assign reviewed matriculation number' }).closest('form'));
    await waitFor(() => expect(api.promoteStudentIdentifier).toHaveBeenCalledWith('student-uuid', 'EEE/2026/001', 'utme', '000123'));
  });
});

describe('reviewed master mark-sheet result uploads', () => {
  it('does not load import history without a staff scope', () => {
    imports({ role: 'student', is_staff: false, permissions: [] }); expect(screen.getByText('Import access unavailable')).toBeTruthy(); expect(api.listRecordImports).not.toHaveBeenCalled();
  });
  it('preserves CSV text and requires review plus a reason for every score correction', async () => {
    imports(); await previewFile();
    expect(api.previewRecordImport).toHaveBeenCalledWith({ kind: 'results', request_id: expect.any(String), filename: 'results.csv', csv_text: csv });
    expect(api.prepareRecordImport.mock.calls[0][1].attempt_number).toBe('');
    expect(screen.queryByRole('heading', { name: 'Converted score sheet' })).toBeNull();
    expect(screen.getByText('New result')).toBeTruthy(); expect(screen.getByText('Score correction')).toBeTruthy();
    const button = screen.getByRole('button', { name: 'Commit reviewed import' }); expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('I reviewed the scores, excluded entries and any corrections against the original mark sheet.')); expect(button.disabled).toBe(true);
    approve(); fireEvent.click(button); await screen.findByRole('heading', { name: 'Import completed' });
    expect(api.commitRecordImport).toHaveBeenCalledWith('import-uuid', { preview_digest: 'review-digest', correction_approvals: [{ row_number: 4, reason: 'Compared with the approved corrected sheet.' }] });
  });
  it('invalidates a preview when the file changes', async () => {
    imports(); await previewFile(); fireEvent.change(sourceInput(), { target: { files: [file('other.csv')] } });
    expect(screen.queryByRole('heading', { name: 'Review import' })).toBeNull(); expect(screen.queryByRole('button', { name: 'Commit reviewed import' })).toBeNull();
  });
  it('blocks the whole import and links unknown students to scoped registration', async () => {
    api.previewRecordImport.mockResolvedValue({ ...batch, can_commit: false, summary: { ...batch.summary, blocked: 1 }, rows: [{ row_number: 2, identifier_type: 'utme', identifier_value: '000999', action: 'blocked', code: 'unknown_student', message: 'Student not registered.' }] });
    imports(); await previewFile(); expect(screen.getByText('Student not registered.')).toBeTruthy();
    expect(screen.getByText('Awaiting student registration')).toBeTruthy(); expect(api.createStudent).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: 'Register or check student separately' }).getAttribute('href')).toBe('/portal/hod/students?register=000999&identifier_type=utme');
    expect(screen.getByRole('button', { name: 'Commit reviewed import' }).disabled).toBe(true);
  });
  it('recovers an uncertain commit through GET without resending the transaction', async () => {
    api.commitRecordImport.mockRejectedValueOnce(new api.ApiError('Network interrupted.', 0)); api.getRecordImport.mockResolvedValue(committed);
    imports(); await previewFile(); approve(); fireEvent.click(screen.getByRole('button', { name: 'Commit reviewed import' }));
    await screen.findByText('The import outcome is uncertain. Check the saved receipt before trying another import.');
    expect(sourceInput().disabled).toBe(true); fireEvent.click(screen.getByRole('button', { name: 'Check saved receipt' }));
    await screen.findByRole('heading', { name: 'Saved receipt recovered' }); expect(api.commitRecordImport).toHaveBeenCalledOnce(); expect(api.getRecordImport).toHaveBeenCalledWith('import-uuid');
  });
  it('retains the request ID when explicitly recovering an uncertain preview', async () => {
    api.previewRecordImport.mockRejectedValueOnce(new api.ApiError('Network interrupted.', 0)).mockResolvedValueOnce(batch);
    imports(); fireEvent.change(sourceInput(), { target: { files: [file()] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByRole('alert'); fireEvent.click(screen.getByText('Convert and preview scores')); await screen.findByRole('heading', { name: 'Review import' });
    expect(api.previewRecordImport.mock.calls[0][0].request_id).toBe(api.previewRecordImport.mock.calls[1][0].request_id);
  });
  it('requires a fresh review after a stale preview', async () => {
    api.commitRecordImport.mockRejectedValueOnce(new api.ApiError('Records changed.', 409));
    api.refreshRecordImport.mockResolvedValue({ ...batch, preview_digest: 'refreshed-digest', revision: 2 });
    imports(); await previewFile(); approve(); fireEvent.click(screen.getByText('Commit reviewed import'));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('I reviewed the scores, excluded entries and any corrections against the original mark sheet.').disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh preview after changes' }));
    await screen.findByText('Preview refreshed. Review all rows and corrections again before importing.');
    expect(screen.getByRole('button', { name: 'Commit reviewed import' }).disabled).toBe(true); expect(sourceInput().value).toBe('');
    approve(); fireEvent.click(screen.getByText('Commit reviewed import')); await screen.findByRole('heading', { name: 'Import completed' });
    expect(api.commitRecordImport.mock.calls[1][1].preview_digest).toBe('refreshed-digest');
  });
  it('offers only result uploads and leaves the reviewed attempt blank', async () => {
    imports();
    expect(screen.queryByLabelText('Import type')).toBeNull();
    expect(screen.queryByText('Student pre-registration list')).toBeNull();
    expect(screen.getByLabelText('Attempt number for converted rows').value).toBe('');
    expect(sourceInput().accept).toContain('.pdf');
    await waitFor(() => expect(api.listRecordImports).toHaveBeenCalledWith(1, expect.any(AbortSignal), 'results'));
    expect(api.createStudent).not.toHaveBeenCalled();
  });
  it('recovers a stored receipt from history without selecting or resending its source file', async () => {
    api.listRecordImports.mockResolvedValue({ results: [{ id: 'import-uuid', filename: 'results.csv', kind: 'results', status: 'committed' }], count: 1, next: null });
    api.getRecordImport.mockResolvedValue(committed); imports();
    fireEvent.click(await screen.findByRole('button', { name: 'Open import results.csv' }));
    await screen.findByRole('heading', { name: 'Saved receipt recovered' });
    expect(api.getRecordImport).toHaveBeenCalledWith('import-uuid'); expect(api.previewRecordImport).not.toHaveBeenCalled(); expect(api.commitRecordImport).not.toHaveBeenCalled();
  });
  it('preserves a UTF-8 BOM and rejects malformed UTF-8 before creating a preview', async () => {
    imports(); const input = sourceInput(); const bad = file(); bad.arrayBuffer = async () => new Uint8Array([0xc3, 0x28]).buffer;
    fireEvent.change(input, { target: { files: [bad] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByRole('alert'); expect(api.previewRecordImport).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { files: [file('bom.csv', '\ufeff' + csv)] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByRole('heading', { name: 'Review import' }); expect(api.previewRecordImport.mock.calls[0][0].csv_text).toBe('\ufeff' + csv);
  });
  it('converts and matches existing converter CSV in one action without saving scores', async () => {
    api.prepareRecordImport.mockResolvedValueOnce({ format: 'student_records_csv', csv_text: csv, filename: 'sample_students-results.csv', source_sha256: 'original-source-digest', summary: { source_course_rows: 2, accepted_rows: 1, unresolved_rows: 1 }, reviewed_context: { attempt_number: 1, include_reviewed_zero_scores: false, context_source: 'source' }, complete_history: false, issues: [{ source_record: 1, source_page: 1, source_table: 0, identifier_value: '001234', course_code: 'EEE302', raw_result: 'NG', code: 'unresolved_score', message: 'NG is not a numeric score.' }], trace: [] });
    imports();
    fireEvent.change(sourceInput(), { target: { files: [file('sample_students.csv', 'name,matric,courses\nSynthetic,001234,"[]"\n')] } });
    fireEvent.change(screen.getByLabelText('Attempt number for converted rows'), { target: { value: '1' } });
    fireEvent.click(screen.getByText('Convert and preview scores')); await screen.findByRole('heading', { name: 'Converted score sheet' });
    expect(screen.getByText('NG is not a numeric score.')).toBeTruthy();
    const report = JSON.parse(decodeURIComponent(screen.getByRole('link', { name: 'Download conversion report' }).getAttribute('href').split(',').slice(1).join(',')));
    expect(report).toMatchObject({ format: 'student_records_csv', source_sha256: 'original-source-digest', reviewed_context: { attempt_number: 1 }, complete_history: false });
    await screen.findByRole('heading', { name: 'Review import' });
    expect(screen.queryByRole('button', { name: 'Preview reviewed results against database' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Commit reviewed import' }).disabled).toBe(true);
    expect(api.previewRecordImport).toHaveBeenCalledWith({ kind: 'results', request_id: expect.any(String), filename: 'sample_students-results.csv', csv_text: csv });
    expect(api.prepareRecordImport.mock.calls[0][1].attempt_number).toBe('1'); expect(api.commitRecordImport).not.toHaveBeenCalled();
  });
  it('accepts PDF directly and keeps preparation errors actionable', async () => {
    imports(); api.prepareRecordImport.mockRejectedValueOnce(new api.ApiError('This PDF has no readable result table; use a reviewed text extraction.', 400));
    fireEvent.change(sourceInput(), { target: { files: [file('mark-sheet.pdf', '%PDF-synthetic')] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByRole('alert'); expect(screen.getByRole('alert').textContent).toContain('no readable result table'); expect(api.prepareRecordImport).toHaveBeenCalledOnce(); expect(api.previewRecordImport).not.toHaveBeenCalled();
  });
  it('invalidates extracted rows when source context changes and rejects unsupported files', async () => {
    api.prepareRecordImport.mockResolvedValueOnce({ format: 'master_sheet_pdf', csv_text: csv, filename: 'sheet-results.csv', source_sha256: 'source', summary: { source_course_rows: 1, accepted_rows: 1, unresolved_rows: 0 }, issues: [], trace: [] });
    imports();
    fireEvent.change(sourceInput(), { target: { files: [file('sheet.pdf', '%PDF-synthetic')] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByRole('heading', { name: 'Converted score sheet' });
    fireEvent.change(screen.getByLabelText('Academic session for source context'), { target: { value: '2025/2026' } }); expect(screen.queryByRole('heading', { name: 'Converted score sheet' })).toBeNull();
    fireEvent.change(sourceInput(), { target: { files: [file('sheet.xlsx', 'not a CSV')] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByText('Choose a CSV or PDF mark sheet. Export Excel workbooks as CSV UTF-8 first.'); expect(api.prepareRecordImport).toHaveBeenCalledOnce();
  });
  it('allows result upload without permission to create students', async () => {
    imports({ ...adviser, permissions: adviser.permissions.filter((permission) => permission !== 'students.add_student') });
    await previewFile();
    expect(api.prepareRecordImport).toHaveBeenCalledOnce();
    expect(api.previewRecordImport.mock.calls[0][0].kind).toBe('results');
    expect(api.createStudent).not.toHaveBeenCalled();
  });
  it('shows only issues when no scores are ready and does not request a database preview', async () => {
    api.prepareRecordImport.mockResolvedValueOnce({ format: 'master_sheet_pdf', csv_text: csv.split('\r\n')[0] + '\r\n', filename: 'sheet-results.csv', source_sha256: 'source', summary: { source_course_rows: 1, accepted_rows: 0, unresolved_rows: 1 }, issues: [{ raw_result: '0NG', code: 'unresolved_mark', message: 'NG remains undecided.' }], trace: [] });
    imports(); fireEvent.change(sourceInput(), { target: { files: [file('sheet.pdf', '%PDF-synthetic')] } }); fireEvent.click(screen.getByText('Convert and preview scores'));
    await screen.findByText('No scores are ready for database matching. Resolve the entries below, then convert the source again.');
    expect(screen.getByText('NG remains undecided.')).toBeTruthy(); expect(api.previewRecordImport).not.toHaveBeenCalled(); expect(api.commitRecordImport).not.toHaveBeenCalled();
  });
  it('does not expose result upload to a student-registration-only account', () => {
    imports({ ...adviser, permissions: ['students.view_student', 'students.add_student'] });
    expect(screen.getByText('Import access unavailable')).toBeTruthy(); expect(api.listRecordImports).not.toHaveBeenCalled();
  });
});
