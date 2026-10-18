import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import ResetPassword from './ResetPassword';
import PortalNotice from './PortalNotice';
import { confirmPasswordReset } from '../api';

vi.mock('../api', () => ({ confirmPasswordReset: vi.fn(), requestPasswordReset: vi.fn() }));
function Location() { const location = useLocation(); return <p data-testid="location">{location.search}</p>; }
function show(path = '/reset-password?uid=MQ&token=synthetic-token') {
  render(<MemoryRouter initialEntries={[path]}><ResetPassword /><Location /></MemoryRouter>);
}
describe('password reset completion', () => {
  it('posts the email-link credentials and clears the URL after success', async () => {
    confirmPasswordReset.mockResolvedValue({}); show();
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'New-pass-123' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'New-pass-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));
    await screen.findByText('Password reset. Sign in with your new password.');
    expect(confirmPasswordReset).toHaveBeenCalledWith('MQ', 'synthetic-token', 'New-pass-123');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe(''));
  });
  it('keeps invalid/expired server errors visible', async () => {
    confirmPasswordReset.mockRejectedValue(new Error('The reset link is invalid or expired.')); show();
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'New-pass-123' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'New-pass-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));
    expect((await screen.findByRole('alert')).textContent).toContain('invalid or expired');
  });
  it('does not show a submit form for incomplete reset links', () => {
    show('/reset-password?uid=MQ');
    expect(screen.getByRole('alert').textContent).toContain('incomplete');
    expect(screen.queryByRole('button', { name: 'Set new password' })).toBeNull();
  });
  it('completes links sent to the older recover-password route', async () => {
    confirmPasswordReset.mockResolvedValue({});
    render(<MemoryRouter initialEntries={['/recover-password?uid=MQ&token=synthetic-token']}><Routes><Route path="/recover-password" element={<PortalNotice />} /><Route path="/reset-password" element={<ResetPassword />} /></Routes><Location /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText('New password'), { target: { value: 'New-pass-123' } });
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'New-pass-123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe(''));
    expect(screen.getByText('Password reset. Sign in with your new password.')).toBeTruthy();
  });
});
