import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import ResetPassword from '../pages/ResetPassword';
import * as api from '../api';

vi.mock('../api', async (original) => ({ ...await original(), confirmPasswordReset: vi.fn(), login: vi.fn() }));
function RouteProbe() { const location = useLocation(); return <output data-testid="reset-location">{location.pathname}{location.search}{location.hash}</output>; }
function resetPage(path = '/reset-password#uid=synthetic-uid&token=private-reset-token', nextLink) {
  return render(<StrictMode><MemoryRouter initialEntries={[path]}><Routes><Route path="/reset-password" element={<><ResetPassword /><RouteProbe />{nextLink && <Link to={nextLink}>Open new reset link</Link>}</>} /><Route path="/login" element={<p>Sign-in page</p>} /></Routes></MemoryRouter></StrictMode>);
}
function passwords(password = 'synthetic-new-password', confirmation = password) {
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: password } }); fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: confirmation } });
}
beforeEach(() => { vi.clearAllMocks(); api.confirmPasswordReset.mockResolvedValue({ detail: 'Password reset.' }); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('private password reset links', () => {
  it('captures and removes a fragment under StrictMode, then resets without signing in or storing credentials', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem'); resetPage(); await waitFor(() => expect(screen.getByTestId('reset-location').textContent).toBe('/reset-password'));
    passwords(); fireEvent.click(screen.getByRole('button', { name: 'Reset password' })); await screen.findByText('Your password has been reset.');
    expect(api.confirmPasswordReset).toHaveBeenCalledWith('synthetic-uid', 'private-reset-token', 'synthetic-new-password'); expect(api.login).not.toHaveBeenCalled(); expect(storage).not.toHaveBeenCalled(); expect(screen.queryByLabelText('New password')).toBeNull();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/login');
  });
  it('accepts legacy query links while removing only secret query values from the URL', async () => {
    resetPage('/reset-password?uid=legacy-uid&token=legacy-token&source=email'); await waitFor(() => expect(screen.getByTestId('reset-location').textContent).toBe('/reset-password?source=email'));
    passwords(); fireEvent.click(screen.getByRole('button', { name: 'Reset password' })); await screen.findByText('Your password has been reset.'); expect(api.confirmPasswordReset).toHaveBeenCalledWith('legacy-uid', 'legacy-token', 'synthetic-new-password');
  });
  it('checks matching confirmation locally and shows an invalid or expired server response', async () => {
    api.confirmPasswordReset.mockRejectedValueOnce(new api.ApiError('This link is invalid or expired.', 400)); resetPage(); passwords('new-password', 'different'); fireEvent.click(screen.getByRole('button', { name: 'Reset password' }));
    await screen.findByText('The passwords do not match.'); expect(api.confirmPasswordReset).not.toHaveBeenCalled(); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Reset password' })); await screen.findByText('This link is invalid or expired.'); expect(api.confirmPasswordReset).toHaveBeenCalledOnce();
  });
  it.each([new api.ApiError('Network interrupted.', 0), new api.ApiError('Unexpected response type.', 200), new SyntaxError('Truncated success response.')])('locks an uncertain password change instead of repeating it (%s)', async (error) => {
    api.confirmPasswordReset.mockRejectedValueOnce(error); resetPage(); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Reset password' })); await screen.findByRole('link', { name: 'Try signing in' });
    expect(screen.getByRole('alert').textContent).toContain('password may already have changed'); expect(screen.queryByRole('button', { name: 'Reset password' })).toBeNull(); expect(api.confirmPasswordReset).toHaveBeenCalledOnce();
  });
  it.each(['/reset-password#uid=new-uid&token=new-token', '/reset-password?uid=new-uid&token=new-token'])('uses a new same-page link and ignores a late old response (%s)', async (nextLink) => {
    let finishOld;
    api.confirmPasswordReset.mockImplementationOnce(() => new Promise((resolve) => { finishOld = resolve; })).mockResolvedValueOnce({ detail: 'New link reset.' });
    resetPage(undefined, nextLink); passwords(); fireEvent.click(screen.getByRole('button', { name: 'Reset password' })); await waitFor(() => expect(api.confirmPasswordReset).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole('link', { name: 'Open new reset link' })); await waitFor(() => expect(screen.getByTestId('reset-location').textContent).toBe('/reset-password')); expect(screen.getByLabelText('New password').value).toBe('');
    finishOld({ detail: 'Old link reset.' }); await waitFor(() => expect(screen.queryByText('Your password has been reset.')).toBeNull());
    passwords('different-new-password'); fireEvent.click(screen.getByRole('button', { name: 'Reset password' })); await screen.findByText('Your password has been reset.');
    expect(api.confirmPasswordReset.mock.calls[1]).toEqual(['new-uid', 'new-token', 'different-new-password']); expect(api.login).not.toHaveBeenCalled();
  });
  it('does not submit an incomplete link', async () => {
    resetPage('/reset-password#uid=uid-only'); await screen.findByText('This reset link is incomplete. Request a new link.'); expect(screen.queryByRole('button', { name: 'Reset password' })).toBeNull(); expect(api.confirmPasswordReset).not.toHaveBeenCalled();
  });
});
