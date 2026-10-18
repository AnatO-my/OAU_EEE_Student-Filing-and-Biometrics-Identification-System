import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../auth/context';
import AttendanceDashboard, { PendingCaptureUpload } from './AttendanceDashboard';
import * as api from '../api';

vi.mock('../api', () => ({ getAttendanceSession: vi.fn(), getCurrentAcademicSession: vi.fn(), listAttendanceRecords: vi.fn(), listAttendanceSessions: vi.fn(), previewPendingCaptures: vi.fn(), importPendingCaptures: vi.fn(), getMyAttendance: vi.fn() }));
const user = { id: 2, role: 'staff', is_staff: true, permissions: ['attendance.view_attendance'] };
const listing = { count: 2, next: null, results: [{ id: 'class-a', title: 'Synthetic Class A', status: 'open', starts_at: '2026-10-18T10:00:00Z' }, { id: 'class-b', title: 'Synthetic Class B', status: 'closed' }] };
beforeEach(() => { vi.clearAllMocks(); api.listAttendanceSessions.mockResolvedValue(listing); api.getAttendanceSession.mockResolvedValue(listing.results[0]); api.listAttendanceRecords.mockResolvedValue({ count: 0, next: null, results: [] }); });
function show() { render(<MemoryRouter><AuthContext.Provider value={{ user, status: 'ready', signOut: vi.fn() }}><AttendanceDashboard /></AuthContext.Provider></MemoryRouter>); }
describe('staff class attendance', () => {
  it('loads the selected class records instead of student own-history', async () => {
    show(); await screen.findByText('1 open classes on this page.');
    fireEvent.change(screen.getByLabelText('Class'), { target: { value: 'class-b' } });
    await screen.findByText('No attendance records have been recorded for this class.');
    expect(api.listAttendanceRecords).toHaveBeenCalledWith('class-b', 1, expect.any(AbortSignal));
    expect(api.getMyAttendance).not.toHaveBeenCalled();
    expect(screen.queryByText('Adebayo Olumide')).toBeNull();
  });
  it('shows server errors and never describes sample records as live', async () => {
    api.listAttendanceSessions.mockRejectedValue(new Error('Attendance server unavailable.')); show();
    expect((await screen.findByRole('alert')).textContent).toContain('unavailable');
    expect(screen.queryByText('Connected')).toBeNull();
    expect(screen.queryByText('Adebayo Olumide')).toBeNull();
    expect(screen.queryByRole('table')).toBeNull();
  });
  it('loads subsequent class pages explicitly', async () => {
    api.listAttendanceSessions.mockResolvedValue({ ...listing, next: '/api/attendance/sessions/?page=2' }); show();
    fireEvent.click(await screen.findByRole('button', { name: 'Next page' }));
    await waitFor(() => expect(api.listAttendanceSessions).toHaveBeenCalledWith(2, expect.any(AbortSignal)));
  });
  it('discards late records from the previously selected class', async () => {
    let finish;
    api.listAttendanceRecords.mockImplementation(id => id === 'class-a' ? new Promise(resolve => { finish = resolve; }) : Promise.resolve({ count: 0, next: null, results: [] }));
    show(); await screen.findByText('1 open classes on this page.');
    fireEvent.change(screen.getByLabelText('Class'), { target: { value: 'class-a' } });
    await waitFor(() => expect(finish).toBeTypeOf('function'));
    fireEvent.change(screen.getByLabelText('Class'), { target: { value: 'class-b' } });
    await screen.findByText('No attendance records have been recorded for this class.');
    finish({ count: 1, next: null, results: [{ id: 1, student_id: 'previous-class-student', status: 'present', reason: 'Old class' }] });
    await waitFor(() => expect(screen.queryByText('previous-class-student')).toBeNull());
  });
});
describe('capture review and retry', () => {
  it('imports only after review and recovers uncertain submissions with the identical bytes/hash', async () => {
    const body = new Uint8Array([123, 125, 10]).buffer;
    const file = new File(['{}\n'], 'synthetic.jsonl');
    file.arrayBuffer = async () => body;
    api.previewPendingCaptures.mockResolvedValue({ batch_id: 'batch-a', file_sha256: 'a'.repeat(64), event_count: 1, new_events: 1, existing_events: 0 });
    api.importPendingCaptures.mockRejectedValueOnce(new Error('Connection lost.')).mockResolvedValueOnce({ receipt_id: 'receipt-a', new_events: 1, existing_events: 0, replayed: true });
    render(<PendingCaptureUpload sessionId="class-a" />);
    fireEvent.change(screen.getByLabelText('Capture file'), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Preview captures' }));
    const confirm = await screen.findByRole('button', { name: 'Confirm import' });
    expect(confirm.disabled).toBe(true);
    expect(api.importPendingCaptures).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(confirm);
    const retry = await screen.findByRole('button', { name: 'Retry same import' });
    expect(screen.getByLabelText('Capture file').disabled).toBe(true);
    fireEvent.click(retry);
    await screen.findByText('Import receipt: receipt-a');
    expect(api.importPendingCaptures).toHaveBeenCalledTimes(2);
    for (const call of api.importPendingCaptures.mock.calls) expect(call).toEqual(['class-a', body, 'a'.repeat(64)]);
    expect(api.previewPendingCaptures).toHaveBeenCalledTimes(1);
  });
});
