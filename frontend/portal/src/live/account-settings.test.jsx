import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../auth/context';
import AccountSettings from './AccountSettings';
import * as api from '../api';

vi.mock('../api', async (original) => ({ ...await original(), changePassword: vi.fn(), getCurrentUser: vi.fn(), getAdministrationOptions: vi.fn(), listManagedStaff: vi.fn(), createManagedStaff: vi.fn(), updateManagedStaff: vi.fn(), listAdviserAssignments: vi.fn(), createAdviserAssignment: vi.fn(), updateAdviserAssignment: vi.fn(), transferHod: vi.fn(), apiRequest: vi.fn() }));
const hod = { id: 1, username: 'synthetic_hod', role: 'hod', is_staff: true, is_superuser: true };
const colleague = { id: 2, username: 'synthetic_adviser', first_name: 'Synthetic', last_name: 'Adviser', email: 'adviser@example.test', is_active: true, is_hod: false, can_transfer: true, direct_permissions: ['students.view_student'], inherited_permissions: ['academics.view_result'], groups: ['Student Readers'] };
const nextStaff = { id: 3, username: 'synthetic_editor', first_name: 'Synthetic', last_name: 'Editor', email: '', is_active: true, is_hod: false, can_transfer: true, direct_permissions: [], inherited_permissions: [], groups: [] };
const options = { permissions: [{ code: 'students.view_student', label: 'View student records' }, { code: 'students.add_student', label: 'Register students' }, { code: 'academics.view_result', label: 'View academic results' }], academic_sessions: [{ id: 9, name: '2026/2027' }], current_academic_session: '2026/2027' };
const page = (results, next = null) => ({ results, count: results.length, next, previous: null });

function account(user = hod, refreshUser = vi.fn().mockResolvedValue({ ...hod, role: 'staff', is_superuser: false })) {
  return render(<AuthContext.Provider value={{ user, refreshUser, status: 'ready' }}><MemoryRouter initialEntries={['/settings']}><Routes><Route path="/settings" element={<AccountSettings user={user} />} /><Route path="/portal/staff/account" element={<p>Ordinary staff account settings</p>} /><Route path="/login" element={<p>Login page</p>} /></Routes></MemoryRouter></AuthContext.Provider>);
}
async function ready() { await screen.findByRole('button', { name: 'Add staff member' }); await screen.findByLabelText('New HOD'); }
async function prepareTransfer() {
  await ready(); fireEvent.change(screen.getByLabelText('New HOD'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('Type the new HOD’s username'), { target: { value: 'synthetic_adviser' } });
  fireEvent.click(screen.getByLabelText('I reviewed the selected staff member and understand that access changes only after acceptance.'));
}
beforeEach(() => {
  vi.clearAllMocks(); api.getAdministrationOptions.mockResolvedValue(options);
  api.listManagedStaff.mockResolvedValue(page([colleague, nextStaff])); api.listAdviserAssignments.mockResolvedValue(page([]));
  api.changePassword.mockResolvedValue({}); api.createManagedStaff.mockResolvedValue(nextStaff); api.updateManagedStaff.mockResolvedValue(colleague);
  api.createAdviserAssignment.mockResolvedValue({ id: 8 }); api.updateAdviserAssignment.mockResolvedValue({ id: 8 });
});
afterEach(cleanup);

describe('account settings and department management', () => {
  it('keeps ordinary staff on password settings without loading HOD management APIs', () => {
    account({ ...hod, role: 'staff', is_superuser: false });
    expect(screen.getByLabelText('Current password')).toBeTruthy(); expect(screen.queryByRole('heading', { name: 'Department settings' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Password' }).getAttribute('href')).toBe('#account-password'); expect(screen.queryByRole('link', { name: 'HOD transfer' })).toBeNull();
    expect(api.getAdministrationOptions).not.toHaveBeenCalled(); expect(api.listManagedStaff).not.toHaveBeenCalled(); expect(api.listAdviserAssignments).not.toHaveBeenCalled();
  });
  it('preserves current-password change and rejects mismatched confirmation before sending', async () => {
    account({ ...hod, role: 'student', is_staff: false, is_superuser: false });
    fireEvent.change(screen.getByLabelText('Current password'), { target: { value: 'old-private' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-private' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'different' } });
    fireEvent.click(screen.getByRole('button', { name: 'Change password' })); await screen.findByText('The new passwords do not match.'); expect(api.changePassword).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'new-private' } }); fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    await screen.findByText('Your password has been changed.'); expect(api.changePassword).toHaveBeenCalledWith('old-private', 'new-private'); expect(screen.getByLabelText('Current password').value).toBe('');
  });
  it('creates ordinary staff with only selected catalog permissions and no privilege flags', async () => {
    account(); await ready(); fireEvent.click(screen.getByRole('button', { name: 'Add staff member' }));
    fireEvent.change(screen.getByLabelText('Staff username'), { target: { value: 'new_synthetic' } });
    fireEvent.change(screen.getByLabelText('Initial password'), { target: { value: 'synthetic-initial-password' } });
    fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'New' } }); fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'Staff' } });
    fireEvent.change(screen.getByLabelText('Staff email'), { target: { value: 'new@example.test' } }); fireEvent.click(screen.getByLabelText('Register students'));
    fireEvent.click(screen.getByRole('button', { name: 'Create staff account' }));
    await waitFor(() => expect(api.createManagedStaff).toHaveBeenCalledWith({ username: 'new_synthetic', password: 'synthetic-initial-password', first_name: 'New', last_name: 'Staff', email: 'new@example.test', is_active: true, permission_codes: ['students.add_student'] }));
    expect(api.transferHod).not.toHaveBeenCalled();
  });
  it('keeps inherited permissions read-only when editing direct staff permissions', async () => {
    account(); fireEvent.click(await screen.findByRole('button', { name: 'Edit synthetic_adviser' }));
    expect(screen.getByLabelText('View student records').checked).toBe(true); expect(screen.getByLabelText('View academic results').checked).toBe(false);
    expect(screen.getByText('Removing a direct permission does not remove the same permission granted by a group.', { exact: false })).toBeTruthy();
    fireEvent.click(screen.getByLabelText('View student records')); fireEvent.click(screen.getByLabelText('Staff account is active')); fireEvent.click(screen.getByRole('button', { name: 'Save staff changes' }));
    await waitFor(() => expect(api.updateManagedStaff).toHaveBeenCalledWith(2, { first_name: 'Synthetic', last_name: 'Adviser', email: 'adviser@example.test', is_active: false, permission_codes: [] }));
  });
  it('assigns recorded sessions and levels using a human staff selector', async () => {
    account(); await ready(); fireEvent.click(screen.getByRole('button', { name: 'Assign part-adviser' }));
    expect(screen.getByLabelText('Assigned staff member').textContent).toContain('Synthetic Adviser (synthetic_adviser)');
    fireEvent.change(screen.getByLabelText('Assigned staff member'), { target: { value: '2' } }); fireEvent.change(screen.getByLabelText('Assigned level'), { target: { value: '300' } });
    expect(screen.getByLabelText('Assignment academic session').value).toBe('2026/2027'); fireEvent.click(screen.getByRole('button', { name: 'Save adviser assignment' }));
    await waitFor(() => expect(api.createAdviserAssignment).toHaveBeenCalledWith({ staff_id: 2, academic_session: '2026/2027', level: 300, is_active: true }));
  });
  it('offers department section shortcuts and excludes the HOD from new adviser assignments', async () => {
    api.listManagedStaff.mockResolvedValue(page([colleague, { ...nextStaff, ...hod, is_hod: true, can_transfer: false }]));
    account(); await ready();
    expect(screen.getByRole('link', { name: 'Staff accounts' }).getAttribute('href')).toBe('#account-staff'); expect(screen.getByRole('link', { name: 'Part-advisers' }).getAttribute('href')).toBe('#account-advisers'); expect(screen.getByRole('link', { name: 'HOD transfer' }).getAttribute('href')).toBe('#account-hod-transfer');
    fireEvent.click(screen.getByRole('button', { name: 'Assign part-adviser' }));
    const choices = within(screen.getByLabelText('Assigned staff member')).getAllByRole('option').map((option) => option.value); expect(choices).toEqual(['', '2']);
  });
  it('reassigns or deactivates a specific adviser assignment without altering the staff account', async () => {
    api.listAdviserAssignments.mockResolvedValue(page([{ id: 8, staff_id: 2, staff_username: 'synthetic_adviser', academic_session: '2026/2027', level: 300, is_active: true }]));
    account(); fireEvent.click(await screen.findByRole('button', { name: 'Edit assignment for synthetic_adviser · 300' }));
    fireEvent.change(screen.getByLabelText('Assigned staff member'), { target: { value: '3' } }); fireEvent.click(screen.getByRole('button', { name: 'Save adviser assignment' }));
    await waitFor(() => expect(api.updateAdviserAssignment).toHaveBeenCalledWith(8, { staff_id: 3, academic_session: '2026/2027', level: 300, is_active: true }));
    fireEvent.click(await screen.findByRole('button', { name: 'Deactivate synthetic_adviser · 300' }));
    await waitFor(() => expect(api.updateAdviserAssignment).toHaveBeenCalledWith(8, { is_active: false })); expect(api.updateManagedStaff).not.toHaveBeenCalled();
  });
  it('requires the exact selected username and review before any HOD transfer', async () => {
    account(); await ready(); fireEvent.change(screen.getByLabelText('New HOD'), { target: { value: '2' } });
    const button = screen.getByRole('button', { name: 'Offer HOD handover' }); expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Type the new HOD’s username'), { target: { value: 'wrong-person' } }); fireEvent.click(screen.getByLabelText('I reviewed the selected staff member and understand that access changes only after acceptance.')); expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Type the new HOD’s username'), { target: { value: 'synthetic_adviser' } }); expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('I reviewed the selected staff member and understand that access changes only after acceptance.')); expect(button.disabled).toBe(false); expect(api.transferHod).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('New HOD'), { target: { value: '3' } }); expect(screen.getByLabelText('Type the new HOD’s username').value).toBe(''); expect(screen.getByRole('button', { name: 'Offer HOD handover' }).disabled).toBe(true);
  });
  it('does not offer inactive, current-HOD or ineligible staff as a transfer target', async () => {
    api.listManagedStaff.mockResolvedValue(page([colleague, { ...nextStaff, id: 3, is_active: false }, { ...nextStaff, id: 4, username: 'linked_student_staff', can_transfer: false }, { ...nextStaff, ...hod, is_hod: true, can_transfer: true }]));
    account(); await ready();
    const choices = within(screen.getByLabelText('New HOD')).getAllByRole('option').map((option) => option.value);
    expect(choices).toEqual(['', '2']); expect(api.transferHod).not.toHaveBeenCalled();
  });
  it('offers handover while retaining current HOD access until incoming acceptance', async () => {
    api.apiRequest.mockResolvedValue({ id: 17, state: 'pending', recipient_id: 2 });
    const refreshUser = vi.fn(); account(hod, refreshUser); await prepareTransfer();
    fireEvent.click(screen.getByRole('button', { name: 'Offer HOD handover' }));
    await screen.findByText('Handover offered.', { exact: false });
    expect(api.apiRequest).toHaveBeenCalledWith('/api/workflows/handover/', { method: 'POST', body: { target_id: 2 } });
    expect(api.transferHod).not.toHaveBeenCalled(); expect(refreshUser).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Department settings' })).toBeTruthy();
  });
  it('checks uncertain handover outcomes without automatically offering again', async () => {
    api.apiRequest.mockRejectedValueOnce(new api.ApiError('Connection interrupted.', 0)); api.getCurrentUser.mockResolvedValue(hod);
    account(); await prepareTransfer(); fireEvent.click(screen.getByRole('button', { name: 'Offer HOD handover' }));
    await screen.findByText('Your account currently still shows HOD access.', { exact: false });
    expect(api.apiRequest).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'Check current account' }));
    await waitFor(() => expect(api.getCurrentUser).toHaveBeenCalledTimes(2));
    expect(api.apiRequest).toHaveBeenCalledOnce();
  });
  it('refreshes former HOD authority when an offer is refused after role transfer', async () => {
    api.apiRequest.mockRejectedValueOnce(new api.ApiError('HOD role changed.', 403));
    api.getCurrentUser.mockResolvedValue({ ...hod, role: 'staff', is_superuser: false });
    account(); await prepareTransfer(); fireEvent.click(screen.getByRole('button', { name: 'Offer HOD handover' }));
    await screen.findByText('Ordinary staff account settings');
    expect(api.apiRequest).toHaveBeenCalledOnce(); expect(api.getCurrentUser).toHaveBeenCalledOnce();
  });
  it('loads every active staff page for selectors rather than hiding targets after page one', async () => {
    api.listManagedStaff.mockImplementation(async (query) => query.is_active ? page(query.page === 1 ? [colleague] : [nextStaff], query.page === 1 ? 'page2' : null) : page([colleague]));
    account(); await ready(); const target = screen.getByLabelText('New HOD');
    expect(within(target).getByRole('option', { name: 'Synthetic Editor (synthetic_editor)' })).toBeTruthy(); expect(api.listManagedStaff).toHaveBeenCalledWith({ page: 2, is_active: true }, expect.any(AbortSignal));
  });
});
