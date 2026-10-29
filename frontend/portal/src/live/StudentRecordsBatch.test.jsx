import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../auth/context';
import StudentRecordsBatch from './StudentRecordsBatch';
import * as api from '../api';

vi.mock('../api', async (original) => ({ ...await original(), apiRequest: vi.fn(), getMyStudentProfile: vi.fn(), listStudents: vi.fn(), listManagedStaff: vi.fn() }));
vi.mock('../pages/DocumentUpload', () => ({ default: () => <p>Private document uploader</p> }));
const student = { id: 9, role: 'student', username: 'synthetic-student', is_staff: false };
const staff = { id: 10, role: 'staff', username: 'synthetic-adviser', is_staff: true };
const profile = { student_id: 'student-one', full_name: 'Synthetic Student', identifier_value: 'EEE/001' };
const details = { student_id: 'student-one', can_review: false, phone_number: '08000000000', email: 'student@example.test', guardians: [], requests: [], source_comparisons: [] };
const workflow = '/api/workflows/students/student-one/';
const documents = '/api/students/student-one/documents/';
function open(user, refreshUser = vi.fn()) {
  return render(<AuthContext.Provider value={{ user, refreshUser }}><MemoryRouter><StudentRecordsBatch user={user} /></MemoryRouter></AuthContext.Provider>);
}
beforeEach(() => {
  vi.clearAllMocks();
  api.getMyStudentProfile.mockResolvedValue(profile);
  api.listStudents.mockResolvedValue({ results: [profile], count: 1, next: null });
  api.listManagedStaff.mockResolvedValue({ results: [], count: 0, next: null });
  api.apiRequest.mockImplementation(async (path) => {
    if (path === workflow) return details;
    if (path === documents || path === '/api/workflows/handover/') return [];
    throw new Error(`Unexpected synthetic endpoint ${path}`);
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('student filing and reviewed requests', () => {
  it('uses ordinary contact fields and submits a proposal rather than changing the live profile', async () => {
    api.apiRequest.mockImplementation(async (path, options = {}) => {
      if (options.method === 'POST') return { id: 1, state: 'pending' };
      return path === workflow ? details : [];
    });
    open(student);
    await screen.findByLabelText('Phone number');
    expect(screen.queryByLabelText(/JSON/)).toBeNull();
    fireEvent.change(screen.getByLabelText('Phone number'), { target: { value: '08111111111' } });
    fireEvent.change(screen.getByLabelText('Reason for the change'), { target: { value: 'New contact number' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit for approval' }));
    await screen.findByText('Your request is awaiting part-adviser or HOD review.');
    expect(api.apiRequest).toHaveBeenCalledWith(workflow, { method: 'POST', body: {
      action: 'change_request', kind: 'contact', values: { phone_number: '08111111111', email: 'student@example.test' }, reason: 'New contact number',
    } });
    expect(api.apiRequest.mock.calls.some(([, options]) => options?.method === 'PATCH')).toBe(false);
  });

  it('lets an adviser select a named student and reject a pending replacement with a reason', async () => {
    api.apiRequest.mockImplementation(async (path, options = {}) => {
      if (path === workflow) return { ...details, can_review: true };
      if (path === documents) return [{ document_id: 4, document_type: 'waec', original_filename: 'replacement.pdf', approval_state: 'pending' }];
      if (path === '/api/documents/4/review/' && options.method === 'POST') return { approval_state: 'rejected' };
      return [];
    });
    open(staff);
    fireEvent.click(await screen.findByRole('button', { name: 'Open file for Synthetic Student' }));
    await screen.findByRole('heading', { name: 'WAEC result' });
    expect(screen.queryByLabelText('Student UUID')).toBeNull();
    fireEvent.change(screen.getByLabelText('Decision'), { target: { value: 'reject' } });
    fireEvent.change(screen.getByLabelText('Review reason'), { target: { value: 'Please upload the complete page' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save review' }));
    await screen.findByText('Replacement review saved.');
    expect(api.apiRequest).toHaveBeenCalledWith('/api/documents/4/review/', { method: 'POST', body: { approve: false, reason: 'Please upload the complete page' } });
  });

  it('refreshes the incoming HOD identity only after successful acceptance', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const refreshUser = vi.fn().mockResolvedValue({ ...staff, role: 'hod', is_superuser: true });
    api.apiRequest.mockImplementation(async (path, options = {}) => {
      if (path === '/api/workflows/handover/' && options.method === 'POST') return { state: 'accepted' };
      if (path === '/api/workflows/handover/') return [{ id: 7, recipient_id: staff.id, state: 'pending' }];
      return [];
    });
    open(staff, refreshUser);
    fireEvent.click(await screen.findByRole('button', { name: 'Accept HOD responsibility' }));
    await waitFor(() => expect(refreshUser).toHaveBeenCalledOnce());
    expect(api.apiRequest).toHaveBeenCalledWith('/api/workflows/handover/', { method: 'POST', body: { handover_id: 7 } });
  });
});
