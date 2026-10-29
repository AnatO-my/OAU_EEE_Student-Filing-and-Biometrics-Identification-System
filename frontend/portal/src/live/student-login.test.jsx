import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import StudentLogin from './StudentLogin';
import SetupStudent from '../pages/SetupStudent';
import * as api from '../api';

vi.mock('../api', async (original) => ({ ...await original(), apiRequest: vi.fn(), getStudentLoginAccount: vi.fn(), issueStudentSetupLink: vi.fn(), updateStudentLoginAccount: vi.fn(), emailStudentAccessLink: vi.fn(), confirmStudentSetup: vi.fn(), createStudentAccount: vi.fn(), login: vi.fn() }));
const hod = { id: 1, role: 'hod', is_staff: true, is_superuser: true };
const pending = { id: 21, username: 'EEE/2026/0001', email: '', is_active: true, setup_pending: true };
const issued = { account: pending, uid: 'synthetic-uid', token: 'synthetic-single-use-token', expires_in: 3600 };
let linkedAccounts, emailAvailable;
function metadata(id) { return { account: linkedAccounts[id] || null, preferred_username: id === 'record-two' ? 'EEE/2026/0002' : 'EEE/2026/0001', email_delivery_available: emailAvailable, email_delivery_detail: '' }; }
function card(user = hod, studentId = 'record-one', identifierValue = 'EEE/2026/0001') {
  return render(<MemoryRouter><StudentLogin user={user} studentId={studentId} identifierValue={identifierValue} /></MemoryRouter>);
}
function RouteProbe() { const location = useLocation(); return <output data-testid="setup-location">{location.pathname}{location.hash}</output>; }
function setupPage(path = '/setup-student#uid=synthetic-uid&token=synthetic-single-use-token', nextLink) {
  return render(<StrictMode><MemoryRouter initialEntries={[path]}><Routes><Route path="/setup-student" element={<><SetupStudent /><RouteProbe />{nextLink && <Link to={nextLink}>Open newly issued setup link</Link>}</>} /><Route path="/login" element={<p>Sign-in page</p>} /></Routes></MemoryRouter></StrictMode>);
}
function passwords(password = 'synthetic-private-password', confirmation = password) {
  fireEvent.change(screen.getByLabelText('New student password'), { target: { value: password } });
  fireEvent.change(screen.getByLabelText('Confirm student password'), { target: { value: confirmation } });
}
beforeEach(() => {
  vi.clearAllMocks(); linkedAccounts = {}; emailAvailable = false;
  api.getStudentLoginAccount.mockImplementation(async (id) => metadata(id));
  api.issueStudentSetupLink.mockImplementation(async (id, values) => {
    linkedAccounts[id] = { ...pending, username: values.username || linkedAccounts[id]?.username || pending.username, email: values.email || linkedAccounts[id]?.email || '' };
    return { ...issued, account: linkedAccounts[id] };
  });
  api.confirmStudentSetup.mockResolvedValue({ detail: 'Password set.', username: pending.username });
  api.updateStudentLoginAccount.mockImplementation(async (id, values) => {
    linkedAccounts[id] = { ...linkedAccounts[id], ...(values.use_student_identifier ? { username: metadata(id).preferred_username } : {}), ...('email' in values ? { email: values.email } : {}) }; return metadata(id);
  });
  api.emailStudentAccessLink.mockImplementation(async (id) => ({ account: linkedAccounts[id], kind: linkedAccounts[id].setup_pending ? 'setup' : 'reset', delivery_status: 'accepted', recipient: linkedAccounts[id].email, detail: 'Submitted.' }));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('department temporary-password issuance', () => {
  it('allows assigned staff to submit an email without revealing a credential', async () => {
    api.apiRequest.mockResolvedValue({ delivery_status: 'accepted' });
    card({ id: 2, role: 'staff', is_staff: true });
    fireEvent.change(screen.getByLabelText('Student email'), { target: { value: 'student@example.test' } });
    fireEvent.click(screen.getByRole('button', { name: 'Email temporary password' }));
    await screen.findByText(/Temporary password submitted by email/);
    expect(api.apiRequest).toHaveBeenCalledWith('/api/workflows/students/record-one/', { method: 'POST', body: { action: 'temporary_password', email: 'student@example.test' } });
    expect(screen.queryByText('Private student setup link')).toBeNull();
  });
  it('does not offer department issuance to students', () => {
    card({ id: 3, role: 'student', is_staff: false });
    expect(screen.queryByRole('button')).toBeNull();
  });
  it('reports uncertain mail acceptance without an automatic retry', async () => {
    api.apiRequest.mockResolvedValue({ delivery_status: 'unknown' });
    card(); fireEvent.change(screen.getByLabelText('Student email'), { target: { value: 'student@example.test' } });
    fireEvent.click(screen.getByRole('button', { name: 'Email temporary password' }));
    await screen.findByText(/Email acceptance could not be confirmed/);
    expect(api.apiRequest).toHaveBeenCalledTimes(1);
  });
});

describe('private student password setup', () => {
  it('removes the fragment while retaining its credentials under StrictMode, then sets the password without login', async () => {
    setupPage(); await waitFor(() => expect(screen.getByTestId('setup-location').textContent).toBe('/setup-student'));
    passwords(); fireEvent.click(screen.getByRole('button', { name: 'Set student password' }));
    await screen.findByText('Your password has been set.', { exact: false }); expect(api.confirmStudentSetup).toHaveBeenCalledWith('synthetic-uid', 'synthetic-single-use-token', 'synthetic-private-password');
    expect(screen.getByText(pending.username)).toBeTruthy(); expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/login'); expect(api.login).not.toHaveBeenCalled(); expect(screen.queryByLabelText('New student password')).toBeNull();
  });
  it('checks password confirmation before sending a setup request', async () => {
    setupPage(); passwords('new-private-password', 'different'); fireEvent.click(screen.getByRole('button', { name: 'Set student password' }));
    await screen.findByText('The passwords do not match.'); expect(api.confirmStudentSetup).not.toHaveBeenCalled();
  });
  it('shows invalid or expired setup errors and offers no automatic retry', async () => {
    api.confirmStudentSetup.mockRejectedValueOnce(new api.ApiError('This setup link is invalid or expired.', 400)); setupPage(); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Set student password' }));
    await screen.findByText('This setup link is invalid or expired.'); expect(api.confirmStudentSetup).toHaveBeenCalledOnce(); expect(screen.getByTestId('setup-location').textContent).toBe('/setup-student');
  });
  it('does not accept missing credentials or query-string credentials', () => {
    setupPage('/setup-student?uid=ignored&token=ignored'); expect(screen.getByRole('alert').textContent).toContain('setup link is incomplete'); expect(screen.queryByRole('button', { name: 'Set student password' })).toBeNull(); expect(api.confirmStudentSetup).not.toHaveBeenCalled();
  });
  it('stops resubmission after an uncertain password-set response and offers sign-in', async () => {
    api.confirmStudentSetup.mockRejectedValueOnce(new api.ApiError('Connection interrupted.', 0)); setupPage(); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Set student password' }));
    await screen.findByRole('link', { name: 'Try signing in' }); expect(screen.getByRole('alert').textContent).toContain('password may already have been set'); expect(screen.queryByRole('button', { name: 'Set student password' })).toBeNull(); expect(api.confirmStudentSetup).toHaveBeenCalledOnce();
  });
  it.each([new api.ApiError('Unexpected response type.', 200), new SyntaxError('Truncated JSON body.'), new api.ApiError('Session changed after dispatch.', 401)])('treats an unverifiable success or response as uncertain without a second POST (%s)', async (error) => {
    api.confirmStudentSetup.mockRejectedValueOnce(error); setupPage(); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Set student password' }));
    await screen.findByRole('link', { name: 'Try signing in' }); expect(screen.queryByRole('button', { name: 'Set student password' })).toBeNull(); expect(api.confirmStudentSetup).toHaveBeenCalledOnce();
  });
  it('captures a newly issued fragment in the same route and ignores a late response from the old link', async () => {
    let finishOld;
    api.confirmStudentSetup.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; })).mockResolvedValueOnce({ username: 'student.new-link' });
    setupPage(undefined, '/setup-student#uid=new-uid&token=new-private-token'); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Set student password' }));
    await waitFor(() => expect(api.confirmStudentSetup).toHaveBeenCalledOnce()); fireEvent.click(screen.getByRole('link', { name: 'Open newly issued setup link' }));
    await waitFor(() => expect(screen.getByTestId('setup-location').textContent).toBe('/setup-student')); expect(screen.getByLabelText('New student password').value).toBe('');
    finishOld({ username: 'student.old-link' }); await waitFor(() => expect(screen.queryByText('student.old-link')).toBeNull());
    passwords('different-new-password'); fireEvent.click(screen.getByRole('button', { name: 'Set student password' })); await screen.findByText('student.new-link');
    expect(api.confirmStudentSetup.mock.calls[1]).toEqual(['new-uid', 'new-private-token', 'different-new-password']); expect(api.login).not.toHaveBeenCalled();
  });
});
