import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import StudentLogin from './StudentLogin';
import SetupStudent from '../pages/SetupStudent';
import * as api from '../api';

vi.mock('../api', async (original) => ({ ...await original(), getStudentLoginAccount: vi.fn(), issueStudentSetupLink: vi.fn(), updateStudentLoginAccount: vi.fn(), emailStudentAccessLink: vi.fn(), confirmStudentSetup: vi.fn(), createStudentAccount: vi.fn(), login: vi.fn() }));
const hod = { id: 1, role: 'hod', is_staff: true, is_superuser: true };
const pending = { id: 21, username: 'EEE/2026/0001', email: '', is_active: true, setup_pending: true };
const issued = { account: pending, uid: 'synthetic-uid', token: 'synthetic-single-use-token', expires_in: 3600 };
let linkedAccounts, emailAvailable;
function metadata(id) { return { account: linkedAccounts[id] || null, preferred_username: id === 'record-two' ? 'EEE/2026/0002' : 'EEE/2026/0001', email_delivery_available: emailAvailable, email_delivery_detail: '' }; }
function card(user = hod, studentId = 'record-one', identifierValue = 'EEE/2026/0001') {
  return render(<MemoryRouter><StudentLogin user={user} studentId={studentId} identifierValue={identifierValue} /></MemoryRouter>);
}
async function createLink() {
  await screen.findByLabelText('Student sign-in username');
  fireEvent.click(screen.getByRole('button', { name: 'Create student sign-in and setup link' }));
  await screen.findByRole('button', { name: 'Reveal private setup link' });
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

describe('HOD student login setup', () => {
  it('is unavailable to ordinary staff and never reads account metadata for them', () => {
    card({ ...hod, role: 'staff', is_superuser: false });
    expect(screen.queryByRole('heading', { name: 'Student login' })).toBeNull(); expect(api.getStudentLoginAccount).not.toHaveBeenCalled(); expect(api.issueStudentSetupLink).not.toHaveBeenCalled();
  });
  it('uses the exact matric number including slashes and leading zeros without a HOD password', async () => {
    card(); const username = await screen.findByLabelText('Student sign-in username'); expect(username.value).toBe('EEE/2026/0001'); expect(username.readOnly).toBe(true);
    expect(document.querySelector('input[type="password"]')).toBeNull(); fireEvent.change(screen.getByLabelText('Student recovery email (optional)'), { target: { value: 'student@example.test' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create student sign-in and setup link' })); await screen.findByRole('button', { name: 'Reveal private setup link' });
    expect(api.issueStudentSetupLink).toHaveBeenCalledWith('record-one', { username: 'EEE/2026/0001', email: 'student@example.test' }); expect(api.createStudentAccount).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Password setup link')).toBeNull(); fireEvent.click(screen.getByRole('button', { name: 'Reveal private setup link' }));
    const link = screen.getByLabelText('Password setup link'); const url = new URL(link.value);
    expect(link.readOnly).toBe(true); expect(url.origin).toBe(window.location.origin); expect(url.pathname).toBe('/setup-student'); expect(url.search).toBe(''); expect(new URLSearchParams(url.hash.slice(1)).get('token')).toBe(issued.token);
    expect(screen.getByText('Single use; valid for up to 60 minutes from issue.', { exact: false })).toBeTruthy();
  });
  it('copies a private link only on request and stores no token in browser storage', async () => {
    const writeText = vi.fn().mockResolvedValue(); vi.stubGlobal('navigator', { clipboard: { writeText } }); const storage = vi.spyOn(Storage.prototype, 'setItem');
    card(); await createLink(); expect(writeText).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: 'Copy private setup link' }));
    await screen.findByText('Private setup link copied. Share it only with this student.'); expect(writeText).toHaveBeenCalledOnce(); expect(writeText.mock.calls[0][0]).toContain('/setup-student#'); expect(storage).not.toHaveBeenCalled();
  });
  it('reissues only a pending setup after explicit invalidation review and sends an empty body', async () => {
    linkedAccounts['record-one'] = pending; card(); await screen.findByText('Waiting for the student to set a password');
    expect(screen.queryByLabelText('Student sign-in username')).toBeNull(); const button = screen.getByRole('button', { name: 'Reissue private setup link' }); expect(button.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('I understand that a new setup link invalidates all previous setup links for this account.')); fireEvent.click(button);
    await screen.findByRole('button', { name: 'Reveal private setup link' }); expect(api.issueStudentSetupLink).toHaveBeenCalledWith('record-one', {});
  });
  it('shows a ready account without a setup or reissue action', async () => {
    linkedAccounts['record-one'] = { ...pending, setup_pending: false }; card(); await screen.findByText('Ready to sign in');
    expect(screen.getByText(pending.username)).toBeTruthy(); expect(screen.queryByRole('button', { name: 'Reissue private setup link' })).toBeNull(); expect(screen.queryByRole('button', { name: 'Create student sign-in and setup link' })).toBeNull(); expect(api.issueStudentSetupLink).not.toHaveBeenCalled();
  });
  it('shows inactive accounts without offering a setup link', async () => {
    linkedAccounts['record-one'] = { ...pending, is_active: false }; card(); await screen.findByText('Inactive'); expect(screen.queryByRole('button', { name: 'Reissue private setup link' })).toBeNull(); expect(api.issueStudentSetupLink).not.toHaveBeenCalled();
  });
  it('checks an uncertain creation through GET and requires an explicit pending-link reissue', async () => {
    api.issueStudentSetupLink.mockImplementationOnce(async (id) => { linkedAccounts[id] = pending; throw new api.ApiError('Connection interrupted.', 0); });
    card(); await screen.findByLabelText('Student sign-in username'); fireEvent.click(screen.getByRole('button', { name: 'Create student sign-in and setup link' }));
    await screen.findByText('Waiting for the student to set a password'); expect(screen.getByRole('alert').textContent).toContain('request may have succeeded'); expect(api.issueStudentSetupLink).toHaveBeenCalledOnce(); expect(api.getStudentLoginAccount.mock.calls.length).toBeGreaterThan(1);
    expect(screen.getByRole('button', { name: 'Reissue private setup link' }).disabled).toBe(true); expect(screen.queryByRole('button', { name: 'Reveal private setup link' })).toBeNull();
  });
  it('treats an unverifiable link-issuance response as uncertain and never reveals a fabricated link', async () => {
    api.issueStudentSetupLink.mockResolvedValueOnce({}); card(); await screen.findByLabelText('Student sign-in username'); fireEvent.click(screen.getByRole('button', { name: 'Create student sign-in and setup link' }));
    await screen.findByRole('alert'); expect(screen.getByRole('alert').textContent).toContain('request may have succeeded'); expect(api.issueStudentSetupLink).toHaveBeenCalledOnce(); expect(screen.queryByRole('button', { name: 'Reveal private setup link' })).toBeNull(); expect(screen.getByRole('button', { name: 'Create student sign-in and setup link' }).disabled).toBe(true);
  });
  it('discards a revealed link when the selected student or HOD identity changes', async () => {
    const view = card(); await createLink(); fireEvent.click(screen.getByRole('button', { name: 'Reveal private setup link' })); expect(screen.getByLabelText('Password setup link').value).toContain(issued.token);
    view.rerender(<MemoryRouter><StudentLogin user={hod} studentId="record-two" identifierValue="EEE/2026/0002" /></MemoryRouter>);
    const username = await screen.findByLabelText('Student sign-in username'); expect(username.value).toBe('EEE/2026/0002'); expect(screen.queryByLabelText('Password setup link')).toBeNull();
    view.rerender(<MemoryRouter><StudentLogin user={{ ...hod, role: 'staff', is_superuser: false }} studentId="record-two" /></MemoryRouter>); expect(screen.queryByRole('heading', { name: 'Student login' })).toBeNull();
  });

  it('changes a legacy username only after reviewing the exact current and new identifiers', async () => {
    linkedAccounts['record-one'] = { ...pending, username: 'student.EEE.2026.0001', email: 'student@example.test', setup_pending: false }; card(); await screen.findByText('Ready to sign in');
    expect(api.updateStudentLoginAccount).not.toHaveBeenCalled(); fireEvent.click(screen.getByText('Change existing username to matric number'));
    const button = screen.getByRole('button', { name: 'Use matric number' }); expect(button.disabled).toBe(true);
    expect(screen.getByText('EEE/2026/0001')).toBeTruthy(); expect(screen.getByText('The old username will stop working.', { exact: false })).toBeTruthy();
    fireEvent.click(screen.getByLabelText('I reviewed the current and new student usernames.')); fireEvent.click(button);
    await screen.findByText('Sign-in username updated to the current student identifier.'); expect(api.updateStudentLoginAccount).toHaveBeenCalledOnce();
    expect(api.updateStudentLoginAccount).toHaveBeenCalledWith('record-one', { expected_username: 'student.EEE.2026.0001', expected_email: 'student@example.test', use_student_identifier: true, expected_identifier_value: 'EEE/2026/0001' });
    expect(api.issueStudentSetupLink).not.toHaveBeenCalled(); expect(document.querySelector('input[type="password"]')).toBeNull();
  });

  it('saves a recovery email using the expected current account values before offering a reviewed send', async () => {
    emailAvailable = true; linkedAccounts['record-one'] = pending; card(); await screen.findByLabelText('Student recovery email');
    expect(screen.getByRole('button', { name: 'Email private setup link' }).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Student recovery email'), { target: { value: 'private@example.test' } }); fireEvent.click(screen.getByRole('button', { name: 'Save student email' }));
    await screen.findByText('Student email updated. Review the recipient before sending an access link.'); expect(api.updateStudentLoginAccount).toHaveBeenCalledWith('record-one', { expected_username: pending.username, expected_email: '', email: 'private@example.test' });
    const review = await screen.findByLabelText('I reviewed the recipient address private@example.test and confirm sending this private access link.'); expect(review.checked).toBe(false);
    expect(api.emailStudentAccessLink).not.toHaveBeenCalled(); expect(screen.getByText('Changing this address invalidates previous setup links;', { exact: false })).toBeTruthy();
  });

  it.each([true, false])('submits a reviewed private email link with a fresh recipient acknowledgment (pending=%s)', async (setupPending) => {
    emailAvailable = true; linkedAccounts['record-one'] = { ...pending, email: 'student@example.test', setup_pending: setupPending }; card();
    const review = await screen.findByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.'); const label = setupPending ? 'Email private setup link' : 'Email private reset link';
    expect(screen.getByRole('button', { name: label }).disabled).toBe(true); fireEvent.click(review); fireEvent.click(screen.getByRole('button', { name: label }));
    await screen.findByText('Submitted to email provider: student@example.test.', { exact: false }); expect(api.emailStudentAccessLink).toHaveBeenCalledOnce();
    expect(api.emailStudentAccessLink).toHaveBeenCalledWith('record-one', { expected_username: pending.username, expected_email: 'student@example.test', confirm_reissue: true });
    expect(screen.getByText('provider acceptance does not confirm delivery.', { exact: false })).toBeTruthy();
    const freshReview = await screen.findByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.'); expect(freshReview.checked).toBe(false); expect(screen.getByRole('button', { name: label }).disabled).toBe(true);
  });

  it('keeps email disabled when department email is unconfigured and account changes disabled when inactive', async () => {
    linkedAccounts['record-one'] = { ...pending, username: 'legacy', is_active: false }; card(); await screen.findByText('Inactive');
    expect(screen.getByText('Email delivery is not configured.', { exact: false })).toBeTruthy(); fireEvent.click(screen.getByText('Change existing username to matric number'));
    expect(screen.getByRole('button', { name: 'Use matric number' }).disabled).toBe(true); expect(screen.getByRole('button', { name: 'Save student email' }).disabled).toBe(true); expect(screen.getByRole('button', { name: 'Email private setup link' }).disabled).toBe(true);
  });

  it.each(['unknown', 'generic503', 'network', 'malformed'])('checks the inbox and saved state after an uncertain email outcome without resending (%s)', async (outcome) => {
    emailAvailable = true; linkedAccounts['record-one'] = { ...pending, email: 'student@example.test' };
    if (outcome === 'unknown') api.emailStudentAccessLink.mockResolvedValueOnce({ account: linkedAccounts['record-one'], kind: 'setup', delivery_status: 'unknown', recipient: 'student@example.test', detail: 'Unknown.' });
    else if (outcome === 'malformed') api.emailStudentAccessLink.mockRejectedValueOnce(new api.ApiError('Unexpected response.', 200));
    else api.emailStudentAccessLink.mockRejectedValueOnce(new api.ApiError('Submission interrupted.', outcome === 'generic503' ? 503 : 0));
    card(); fireEvent.click(await screen.findByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.')); fireEvent.click(screen.getByRole('button', { name: 'Email private setup link' }));
    await screen.findByText('Check the student’s inbox, then use Check student account status before requesting another email.'); expect(api.emailStudentAccessLink).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Email private setup link' }).disabled).toBe(true); expect(screen.queryByRole('button', { name: 'Reveal private setup link' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Check student account status' })); const review = await screen.findByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.'); expect(review.disabled).toBe(false); expect(review.checked).toBe(false);
    expect(screen.getByRole('button', { name: 'Email private setup link' }).disabled).toBe(true); expect(api.emailStudentAccessLink).toHaveBeenCalledOnce();
  });

  it('distinguishes a structured preflight config rejection from an uncertain proxy 503', async () => {
    emailAvailable = true; linkedAccounts['record-one'] = { ...pending, email: 'student@example.test' };
    api.emailStudentAccessLink.mockRejectedValueOnce(new api.ApiError('Unavailable.', 503, { code: 'student_email_not_configured' })); card();
    fireEvent.click(await screen.findByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.')); fireEvent.click(screen.getByRole('button', { name: 'Email private setup link' }));
    await screen.findByText('Email delivery is not configured. No email was submitted.', { exact: false }); expect(api.emailStudentAccessLink).toHaveBeenCalledOnce();
    expect(screen.queryByText('Check the student’s inbox, then use Check student account status before requesting another email.')).toBeNull();
    const review = await screen.findByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.'); expect(review.checked).toBe(false);
  });

  it('discards the manually revealed setup token before submitting an email link', async () => {
    emailAvailable = true; card(); await screen.findByLabelText('Student sign-in username'); fireEvent.change(screen.getByLabelText('Student recovery email (optional)'), { target: { value: 'student@example.test' } }); await createLink();
    fireEvent.click(screen.getByRole('button', { name: 'Reveal private setup link' })); expect(screen.getByLabelText('Password setup link').value).toContain(issued.token);
    fireEvent.click(screen.getByLabelText('I reviewed the recipient address student@example.test and confirm sending this private access link.')); fireEvent.click(screen.getByRole('button', { name: 'Email private setup link' })); await screen.findByText('Submitted to email provider:', { exact: false });
    expect(screen.queryByLabelText('Password setup link')).toBeNull(); expect(screen.queryByRole('button', { name: 'Reveal private setup link' })).toBeNull();
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
