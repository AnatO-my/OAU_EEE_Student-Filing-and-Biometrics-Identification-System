import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from './api';

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fetchMock = vi.fn();
beforeEach(() => { api.forgetSession(); fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock); });

describe('session and byte-preserving API adapter', () => {
  it('updates student account details and submits a reviewed email access request with CSRF', async () => {
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'student-account-csrf' })).mockResolvedValueOnce(json({ account: { username: 'EEE/2026/0001' } })).mockResolvedValueOnce(json({ delivery_status: 'accepted', kind: 'setup' }));
    const change = { expected_username: 'student.legacy', expected_email: '', email: 'student@example.test', use_student_identifier: true, expected_identifier_value: 'EEE/2026/0001' };
    const email = { expected_username: 'EEE/2026/0001', expected_email: 'student@example.test', confirm_reissue: true };
    await api.updateStudentLoginAccount('student/one', change); await api.emailStudentAccessLink('student/one', email);
    expect(new URL(fetchMock.mock.calls[1][0]).pathname).toBe('/api/students/student%2Fone/account/'); expect(fetchMock.mock.calls[1][1].method).toBe('PATCH'); expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual(change);
    expect(new URL(fetchMock.mock.calls[2][0]).pathname).toBe('/api/students/student%2Fone/account/email-link/'); expect(fetchMock.mock.calls[2][1].method).toBe('POST'); expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual(email); expect(fetchMock.mock.calls[2][1].headers['X-CSRFToken']).toBe('student-account-csrf');
  });

  it('issues student password setup links without a HOD-chosen password', async () => {
    fetchMock.mockResolvedValueOnce(json({ account: null })).mockResolvedValueOnce(json({ csrfToken: 'setup-csrf' })).mockResolvedValueOnce(json({ uid: 'uid', token: 'synthetic-token', expires_in: 3600 })).mockResolvedValueOnce(json({ uid: 'uid', token: 'replacement', expires_in: 3600 }));
    await api.getStudentLoginAccount('student/one'); await api.issueStudentSetupLink('student/one', { username: 'student.synthetic', email: '' }); await api.issueStudentSetupLink('student/one');
    expect(new URL(fetchMock.mock.calls[0][0]).pathname).toBe('/api/students/student%2Fone/account/');
    expect(new URL(fetchMock.mock.calls[2][0]).pathname).toBe('/api/students/student%2Fone/account/setup-link/'); expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ username: 'student.synthetic', email: '' }); expect(JSON.parse(fetchMock.mock.calls[3][1].body)).toEqual({});
    expect(fetchMock.mock.calls[2][1].headers['X-CSRFToken']).toBe('setup-csrf');
  });

  it('treats public setup rejection as a form error without discarding an existing staff session', async () => {
    const lost = vi.fn(), unsubscribe = api.subscribeSessionLost(lost);
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'setup-csrf' })).mockResolvedValueOnce(json({ detail: 'Setup is unavailable.' }, 403));
    await expect(api.confirmStudentSetup('uid', 'synthetic-token', 'synthetic-new-password')).rejects.toMatchObject({ status: 403 });
    expect(lost).not.toHaveBeenCalled(); expect(fetchMock).toHaveBeenCalledTimes(2); expect(new URL(fetchMock.mock.calls[1][0]).pathname).toBe('/api/auth/student/setup/confirm/');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ uid: 'uid', token: 'synthetic-token', new_password: 'synthetic-new-password' }); unsubscribe();
  });

  it('uses scoped staff-management URLs and authenticated CSRF writes', async () => {
    fetchMock.mockResolvedValueOnce(json({ permissions: [] })).mockResolvedValueOnce(json({ results: [], count: 0 }))
      .mockResolvedValueOnce(json({ csrfToken: 'staff-csrf' })).mockResolvedValueOnce(json({ id: 2 })).mockResolvedValueOnce(json({ id: 2 }))
      .mockResolvedValueOnce(json({ results: [], count: 0 })).mockResolvedValueOnce(json({ id: 8 })).mockResolvedValueOnce(json({ id: 8 }));
    await api.getAdministrationOptions(); await api.listManagedStaff({ page: 2, search: 'Synthetic', is_active: true });
    await api.createManagedStaff({ username: 'synthetic_staff', password: 'synthetic-only', permission_codes: ['students.view_student'] });
    await api.updateManagedStaff(2, { is_active: false }); await api.listAdviserAssignments({ page: 3, academic_session: '2026/2027' });
    await api.createAdviserAssignment({ staff_id: 2, academic_session: '2026/2027', level: 300, is_active: true }); await api.updateAdviserAssignment(8, { is_active: false });
    expect(new URL(fetchMock.mock.calls[0][0]).pathname).toBe('/api/accounts/administration-options/');
    expect(new URL(fetchMock.mock.calls[1][0]).searchParams.get('page')).toBe('2'); expect(new URL(fetchMock.mock.calls[1][0]).searchParams.get('is_active')).toBe('true');
    expect(new URL(fetchMock.mock.calls[3][0]).pathname).toBe('/api/accounts/staff/'); expect(fetchMock.mock.calls[3][1].headers['X-CSRFToken']).toBe('staff-csrf');
    expect(new URL(fetchMock.mock.calls[4][0]).pathname).toBe('/api/accounts/staff/2/'); expect(fetchMock.mock.calls[4][1].method).toBe('PATCH');
    expect(new URL(fetchMock.mock.calls[5][0]).searchParams.get('academic_session')).toBe('2026/2027');
    expect(new URL(fetchMock.mock.calls[6][0]).pathname).toBe('/api/accounts/adviser-assignments/'); expect(new URL(fetchMock.mock.calls[7][0]).pathname).toBe('/api/accounts/adviser-assignments/8/');
  });

  it('sends an explicitly confirmed HOD transfer once without retrying a lost response', async () => {
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'handover-csrf' })).mockRejectedValueOnce(new TypeError('network unavailable'));
    const body = { target_staff_id: 2, expected_target_username: 'synthetic_staff', current_password: 'synthetic-only', confirmation: 'TRANSFER HOD' };
    await expect(api.transferHod(body)).rejects.toMatchObject({ status: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(2); const [url, request] = fetchMock.mock.calls[1];
    expect(new URL(url).pathname).toBe('/api/accounts/transfer-hod/'); expect(request.method).toBe('POST'); expect(JSON.parse(request.body)).toEqual(body); expect(request.headers['X-CSRFToken']).toBe('handover-csrf');
  });

  it('rotates CSRF after login and sends a later write with the rotated token', async () => {
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'before-login' })).mockResolvedValueOnce(json({ id: 7, role: 'hod' }))
      .mockResolvedValueOnce(json({ csrfToken: 'after-login' })).mockResolvedValueOnce(json({ ok: true }));
    await api.login('hod', 'private-value');
    await api.createCourse('EEE101', 'Circuit theory');
    expect(fetchMock.mock.calls[1][1].headers['X-CSRFToken']).toBe('before-login');
    expect(fetchMock.mock.calls[3][1].headers['X-CSRFToken']).toBe('after-login');
    expect(fetchMock.mock.calls[3][1]).toMatchObject({ credentials: 'same-origin', cache: 'no-store' });
  });

  it('uploads the original Blob unchanged and imports with the preview whole-file hash', async () => {
    const file = new Blob(['{"metadata":"preserve whitespace"}\r\n'], { type: 'application/x-ndjson' });
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'csrf' })).mockResolvedValueOnce(json({ file_sha256: 'whole-file-hash' })).mockResolvedValueOnce(json({ receipt_id: 'receipt' }));
    const preview = await api.previewPendingCaptures('class-id', file);
    await api.importPendingCaptures('class-id', file, preview.file_sha256);
    expect(fetchMock.mock.calls[1][1].body).toBe(file);
    expect(fetchMock.mock.calls[1][1].headers['Content-Type']).toBe('application/x-ndjson');
    expect(fetchMock.mock.calls[1][1].headers).not.toHaveProperty('X-Capture-SHA256');
    expect(fetchMock.mock.calls[2][1].body).toBe(file);
    expect(fetchMock.mock.calls[2][1].headers['X-Capture-SHA256']).toBe('whole-file-hash');
  });

  it('prepares converter/PDF sources as multipart without a JSON content type', async () => {
    const file = new File(['%PDF-synthetic'], 'mark-sheet.pdf', { type: 'application/pdf' });
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'csrf' })).mockResolvedValueOnce(json({ format: 'master_sheet_pdf', csv_text: 'prepared' }));
    await api.prepareRecordImport(file, { attempt_number: '1', academic_session: '', include_reviewed_zero_scores: false });
    const [, options] = fetchMock.mock.calls[1];
    expect(options.body).toBeInstanceOf(FormData); expect(options.body.get('file')).toBe(file);
    expect(options.body.get('attempt_number')).toBe('1'); expect(options.body.get('include_reviewed_zero_scores')).toBe('false');
    expect(options.body.has('academic_session')).toBe(false); expect(options.headers).not.toHaveProperty('Content-Type'); expect(options.headers['X-CSRFToken']).toBe('csrf');
  });

  it('keeps the signed-in identity after an action-only permission denial', async () => {
    const lost = vi.fn(), unsubscribe = api.subscribeSessionLost(lost);
    fetchMock.mockResolvedValueOnce(json({ detail: 'Permission denied.' }, 403)).mockResolvedValueOnce(json({ id: 7, role: 'staff' }));
    await expect(api.listResults()).rejects.toMatchObject({ status: 403 });
    expect(lost).not.toHaveBeenCalled(); unsubscribe();
  });

  it('clears the workspace when the session probe confirms expiry', async () => {
    const lost = vi.fn(), unsubscribe = api.subscribeSessionLost(lost);
    fetchMock.mockResolvedValueOnce(json({ detail: 'Authentication required.' }, 403)).mockResolvedValueOnce(json({ detail: 'Authentication required.' }, 403));
    await expect(api.listResults()).rejects.toMatchObject({ status: 403 });
    expect(lost).toHaveBeenCalledOnce(); unsubscribe();
  });

  it('rejects a response that finishes after logout/session replacement', async () => {
    let finish;
    fetchMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    const pending = api.getMyStudentProfile();
    api.forgetSession(); finish(json({ full_name: 'Private record' }));
    await expect(pending).rejects.toMatchObject({ status: 401 });
  });

  it('never retries a failed write automatically', async () => {
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'csrf' })).mockRejectedValueOnce(new TypeError('network unavailable'));
    await expect(api.recordManualAttendance('class', { event_id: 'stable-id' })).rejects.toMatchObject({ status: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not send an old write when the session changes while awaiting CSRF', async () => {
    fetchMock.mockResolvedValueOnce(json({ csrfToken: 'csrf' }));
    await api.getCsrfToken();
    const pending = api.createCourse('EEE101', 'Circuit theory');
    api.forgetSession();
    await expect(pending).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('paginates by page number without following an external next URL', async () => {
    const loader = vi.fn().mockResolvedValueOnce({ results: [1], next: 'https://external.invalid/steal' }).mockResolvedValueOnce({ results: [2], next: null });
    expect(await api.collectPages(loader)).toEqual([1, 2]);
    expect(loader.mock.calls.map(([page]) => page)).toEqual([1, 2]);
  });

  it('filters result upload history before server pagination', async () => {
    fetchMock.mockResolvedValueOnce(json({ results: [], count: 0 }));
    await api.listRecordImports(2, undefined, 'results');
    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe('/api/imports/'); expect(url.searchParams.get('page')).toBe('2'); expect(url.searchParams.get('kind')).toBe('results');
  });
});
