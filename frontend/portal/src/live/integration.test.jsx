import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../auth/context';
import LivePortal from './LivePortal';
import Attendance, { PendingUpload } from './Attendance';
import ResetPassword from '../pages/ResetPassword';
import * as api from '../api';
import { Table } from './ui';
import Records from './Records';

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal();
  return { ...original, listAttendanceSessions: vi.fn(), getMyAttendance: vi.fn(), getAttendanceSession: vi.fn(), listAttendanceRecords: vi.fn(), previewPendingCaptures: vi.fn(), importPendingCaptures: vi.fn(), confirmPasswordReset: vi.fn(), listStudents: vi.fn(), getStudent: vi.fn(), uploadStudentDocument: vi.fn() };
});

afterEach(cleanup);
beforeEach(() => { vi.clearAllMocks(); });
const staff = { id: 8, username: 'staff', role: 'staff', is_staff: true, is_superuser: false, permissions: ['attendance.view_attendance'], adviser_levels: [300] };
const student = { id: 9, username: 'student', role: 'student', is_staff: false, permissions: [] };
function portal(path, auth) {
  return render(<AuthContext.Provider value={{ status: 'ready', error: null, ...auth }}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/portal/:role/:section?" element={<LivePortal />} /><Route path="/login" element={<p>Login page</p>} />
  </Routes></MemoryRouter></AuthContext.Provider>);
}

describe('authenticated live workspace', () => {
  it('shows document upload in the active student record only with document permission', async () => {
    const record = { student_id: 'student-one', full_name: 'Synthetic document student', identifier_type: 'matriculation', identifier_value: 'EEE/2026/001', current_level: 300, is_active: true };
    api.listStudents.mockResolvedValue({ results: [record], count: 1, next: null }); api.getStudent.mockResolvedValue(record);
    const readOnly = { ...staff, permissions: ['students.view_student'] };
    const view = (user) => <MemoryRouter initialEntries={['/?student=student-one']}><Records section="students" user={user} /></MemoryRouter>;
    const page = render(view(readOnly)); await screen.findByRole('heading', { name: 'Student record' }); await screen.findByText('EEE/2026/001', { selector: 'dd' });
    expect(screen.queryByRole('heading', { name: 'Upload student document' })).toBeNull();
    page.rerender(view({ ...readOnly, permissions: [...readOnly.permissions, 'documents.add_studentdocument'] })); expect(screen.getByRole('heading', { name: 'Upload student document' })).toBeTruthy();
    api.uploadStudentDocument.mockResolvedValue({ original_filename: 'synthetic.pdf', status: 'accepted', quality_notes: '' });
    const file = new File(['%PDF-synthetic'], 'synthetic.pdf', { type: 'application/pdf' }); fireEvent.change(screen.getByLabelText('Scanned document'), { target: { files: [file] } });
    fireEvent.click(screen.getByLabelText('I have checked the student, document type and replacement.')); fireEvent.click(screen.getByRole('button', { name: 'Upload document' }));
    await screen.findByText('synthetic.pdf: Accepted.', { exact: false }); expect(api.uploadStudentDocument).toHaveBeenCalledWith('student-one', file, 'result');
  });

  it('does not render a role workspace until the session is checked', () => {
    portal('/portal/hod/dashboard', { user: null, status: 'loading' });
    expect(screen.getByRole('status').textContent).toContain('Checking your session');
    expect(screen.queryByRole('navigation')).toBeNull();
  });

  it('uses the authenticated role instead of a public role URL', async () => {
    portal('/portal/hod/guardian-results', { user: student });
    await screen.findByRole('heading', { name: 'Overview' });
    expect(screen.queryByRole('link', { name: 'Guardian results' })).toBeNull();
    expect(screen.getByRole('link', { name: 'My profile' })).toBeTruthy();
  });

  it('denies an unauthorized section without loading its API', () => {
    portal('/portal/staff/students', { user: staff });
    expect(screen.getByRole('heading', { name: 'This section is unavailable' })).toBeTruthy();
  });

  it('shows Upload results to an assigned result editor without student-registration permission', () => {
    portal('/portal/staff/dashboard', { user: { ...staff, permissions: ['students.view_student', 'academics.view_result', 'academics.add_result'] } });
    expect(screen.getByRole('navigation').textContent).toContain('Upload results');
    expect(screen.queryByRole('link', { name: 'Student intake / imports' })).toBeNull();
  });

  it('does not offer Upload results to a registration-only adviser', () => {
    portal('/portal/staff/dashboard', { user: { ...staff, permissions: ['students.view_student', 'students.add_student'] } });
    expect(screen.queryByRole('link', { name: 'Upload results' })).toBeNull();
  });

  it('calls real signOut and leaves the private portal', async () => {
    const signOut = vi.fn().mockResolvedValue();
    portal('/portal/staff/dashboard', { user: staff, signOut });
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await screen.findByText('Login page'); expect(signOut).toHaveBeenCalledOnce();
  });

  it('supports menu disclosure, Escape, route focus and a skip-to-main link', async () => {
    portal('/portal/staff/dashboard', { user: staff });
    const menu = screen.getByRole('button', { name: 'Menu' });
    expect(menu.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(menu);
    expect(menu.getAttribute('aria-expanded')).toBe('true');
    const account = screen.getByRole('link', { name: 'Account settings' });
    account.focus(); fireEvent.keyDown(account, { key: 'Escape' });
    expect(menu.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(menu);
    fireEvent.click(menu); fireEvent.click(account);
    expect(menu.getAttribute('aria-expanded')).toBe('false');
    expect(await screen.findByRole('heading', { name: 'Account settings' })).toBeTruthy();
    await screen.findByLabelText('Current password');
    expect(document.activeElement).toBe(screen.getByRole('main'));
    menu.focus(); fireEvent.click(screen.getByRole('link', { name: 'Skip to main content' }));
    expect(document.activeElement).toBe(screen.getByRole('main'));
  });

  it('keeps account settings beneath the signed-in identity and outside workspace navigation', async () => {
    portal('/portal/staff/account', { user: staff });
    const account = screen.getByRole('link', { name: 'Account settings' });
    expect(account.closest('.live-identity')).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Portal navigation' }).contains(account)).toBe(false);
    expect(account.getAttribute('aria-current')).toBe('page');
    expect(account.getAttribute('href')).toBe('/portal/staff/account');
    await screen.findByRole('heading', { name: 'Account settings' });
    await screen.findByLabelText('Current password');
    expect(screen.queryByRole('heading', { name: /Transfer department ownership/ })).toBeNull();
  });

  it('keeps a refreshed staff account on account settings after HOD access ends', async () => {
    portal('/portal/hod/account', { user: staff });
    await screen.findByRole('heading', { name: 'Account settings' });
    await screen.findByLabelText('Current password');
    expect(screen.getByRole('link', { name: 'Account settings' }).getAttribute('href')).toBe('/portal/staff/account');
    expect(screen.queryByRole('heading', { name: 'Department settings' })).toBeNull();
  });

  it('provides a keyboard-focusable table region with column headers', () => {
    render(<Table headings={['Student', 'Score']}><tr><td>Synthetic student</td><td>76</td></tr></Table>);
    const region = screen.getByRole('region', { name: /Student, Score table/ });
    expect(region.tabIndex).toBe(0);
    region.focus(); expect(document.activeElement).toBe(region);
    expect(screen.getAllByRole('columnheader').every((header) => header.getAttribute('scope') === 'col')).toBe(true);
  });

  it('uses paginated staff classes and their record endpoint, never student history', async () => {
    api.listAttendanceSessions.mockResolvedValueOnce({ results: [{ id: 'one', title: 'First class', offering: 11, starts_at: '2026-10-21T10:00:00Z', status: 'closed' }], next: 'page2' })
      .mockResolvedValueOnce({ results: [{ id: 'two', title: 'Second class', offering: 12, starts_at: '2026-10-21T11:00:00Z', status: 'open' }], next: null });
    api.getAttendanceSession.mockResolvedValue({ id: 'two', title: 'Second class', student_ids: [], status: 'open' });
    api.listAttendanceRecords.mockResolvedValue({ results: [{ id: 1, student_id: 'student-record', status: 'present', recorded_at: '2026-10-21T11:10:00Z', reason: 'Manual check' }], count: 1, next: null });
    render(<Attendance user={staff} />);
    await screen.findByText('2 accessible classes · 1 open');
    fireEvent.change(screen.getByLabelText('Choose a class'), { target: { value: 'two' } });
    await screen.findByText('student-record');
    expect(api.listAttendanceRecords).toHaveBeenCalledWith('two', 1, expect.any(AbortSignal));
    expect(api.getMyAttendance).not.toHaveBeenCalled();
  });

  it('shows an API error without synthetic attendance records or Connected labels', async () => {
    api.listAttendanceSessions.mockRejectedValue(new Error('Course scope could not be checked.'));
    render(<Attendance user={staff} />);
    expect((await screen.findByRole('alert')).textContent).toContain('Course scope could not be checked.');
    expect(screen.queryByText('Connected')).toBeNull(); expect(screen.queryByText('Adebayo Olumide')).toBeNull();
  });

  it('uses only the student own-history endpoint for student attendance', async () => {
    api.getMyAttendance.mockResolvedValue({ results: [], count: 0, next: null });
    render(<Attendance user={student} />); await screen.findByText('No attendance has been recorded.');
    expect(api.getMyAttendance).toHaveBeenCalledWith(1, expect.any(AbortSignal)); expect(api.listAttendanceSessions).not.toHaveBeenCalled();
  });
});

describe('pending file review and reset completion', () => {
  it('requires review and reuses exact preview bytes/hash when recovering a lost receipt', async () => {
    const file = new File(['raw bytes\r\n'], 'batch.jsonl');
    const preview = { file_sha256: 'whole-file', batch_id: 'batch', event_count: 1, new_events: 1, existing_events: 0, recovery_review_required: true };
    api.previewPendingCaptures.mockResolvedValue(preview);
    api.importPendingCaptures.mockRejectedValueOnce(new Error('Connection interrupted.')).mockResolvedValueOnce({ receipt_id: 'durable-receipt', replayed: true, new_events: 1, existing_events: 0 });
    render(<PendingUpload sessionId="class" />);
    fireEvent.change(screen.getByLabelText(/Capture JSONL file/), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Preview capture file' }));
    await screen.findByText('whole-file');
    const button = screen.getByRole('button', { name: 'Import reviewed capture file' });
    expect(button.disabled).toBe(true); expect(api.importPendingCaptures).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(button);
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: 'Import reviewed capture file' }));
    await screen.findByText('Original receipt recovered');
    expect(api.importPendingCaptures.mock.calls).toEqual([['class', file, 'whole-file'], ['class', file, 'whole-file']]);
  });

  it('invalidates preview when another file is selected', async () => {
    api.previewPendingCaptures.mockResolvedValue({ file_sha256: 'first-file', event_count: 0 });
    render(<PendingUpload sessionId="class" />);
    const input = screen.getByLabelText(/Capture JSONL file/);
    fireEvent.change(input, { target: { files: [new File(['a'], 'a.jsonl')] } }); fireEvent.click(screen.getByText('Preview capture file'));
    await screen.findByText('first-file'); fireEvent.change(input, { target: { files: [new File(['b'], 'b.jsonl')] } });
    expect(screen.queryByText('first-file')).toBeNull(); expect(screen.queryByRole('button', { name: 'Import reviewed capture file' })).toBeNull();
  });

  it('completes the emailed uid/token link using matching new passwords', async () => {
    api.confirmPasswordReset.mockResolvedValue({ detail: 'Password reset.' });
    render(<MemoryRouter initialEntries={['/reset-password?uid=account-id&token=one-use-token']}><ResetPassword /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-value' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'new-password-value' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));
    await waitFor(() => expect(api.confirmPasswordReset).toHaveBeenCalledWith('account-id', 'one-use-token', 'new-password-value'));
    await screen.findByText('Your password has been reset.');
  });
});
