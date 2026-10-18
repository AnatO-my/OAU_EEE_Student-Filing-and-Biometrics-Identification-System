import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import { AuthContext } from './context';
import RequireAuth from './RequireAuth';
import LivePortal from '../pages/LivePortal';
import { workspaceRoles } from './permissions';
import { forgetSession } from '../api';

const staff = { id: 2, username: 'lecturer', first_name: '', last_name: '', role: 'staff', is_staff: true, is_superuser: false, permissions: ['students.view_student'], adviser_levels: [] };
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function app(path, value) {
  const routes = <MemoryRouter initialEntries={[path]}><Routes><Route path="/portal/:role/:section?" element={<RequireAuth><LivePortal /></RequireAuth>} /><Route path="/login" element={<p>Sign in page</p>} /><Route path="/access-denied" element={<p>Access denied</p>} /></Routes></MemoryRouter>;
  return render(value ? <AuthContext.Provider value={value}>{routes}</AuthContext.Provider> : <AuthProvider>{routes}</AuthProvider>);
}
describe('authenticated workspaces', () => {
  it('shows a loading state before deciding whether to redirect', () => {
    app('/portal/hod/dashboard', { user: null, status: 'loading' });
    expect(screen.getByRole('status').textContent).toContain('Checking');
    expect(screen.queryByText('Sign in page')).toBeNull();
  });
  it('redirects anonymous users to login', () => {
    app('/portal/hod/dashboard', { user: null, status: 'ready' });
    expect(screen.getByText('Sign in page')).toBeTruthy();
  });
  it('ignores an HOD URL for an ordinary staff identity and removes the demo role switcher', async () => {
    app('/portal/hod/dashboard', { user: staff, status: 'ready' });
    await screen.findByText('Signed in as lecturer');
    expect(screen.getByText('EEE OAU · staff')).toBeTruthy();
    expect(screen.queryByRole('combobox')).toBeNull();
    expect(workspaceRoles(staff)).toEqual(['staff']);
    expect(workspaceRoles({ ...staff, adviser_levels: [300] })).toEqual(['staff', 'adviser']);
  });
  it('calls real sign-out from the portal button', async () => {
    const signOut = vi.fn().mockResolvedValue(null);
    app('/portal/staff/dashboard', { user: staff, status: 'ready', signOut });
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }));
    await screen.findByText('Sign in page');
    expect(signOut).toHaveBeenCalledTimes(1);
  });
  it('removes attendance content when the account loses the required permission', async () => {
    const view = account => <AuthContext.Provider value={{ user: account, status: 'ready' }}><MemoryRouter initialEntries={['/attendance']}><Routes><Route path="/attendance" element={<RequireAuth staff permission="attendance.view_attendance"><p>Private attendance records</p></RequireAuth>} /><Route path="/access-denied" element={<p>Access denied</p>} /></Routes></MemoryRouter></AuthContext.Provider>;
    const page = render(view({ ...staff, permissions: ['attendance.view_attendance'] }));
    expect(screen.getByText('Private attendance records')).toBeTruthy();
    page.rerender(view({ ...staff, permissions: [] }));
    await screen.findByText('Access denied');
    expect(screen.queryByText('Private attendance records')).toBeNull();
  });
  it('retains a valid session when a resource permission is denied without a request loop', async () => {
    forgetSession();
    const fetch = vi.fn(async url => new URL(url).pathname === '/api/auth/me/' ? json(staff) : json({ detail: 'Permission denied.' }, 403));
    vi.stubGlobal('fetch', fetch);
    app('/portal/staff/students');
    await screen.findByText('Permission denied.');
    await waitFor(() => expect(fetch.mock.calls.filter(([url]) => new URL(url).pathname === '/api/auth/me/')).toHaveLength(2));
    expect(screen.queryByText('Sign in page')).toBeNull();
    expect(fetch.mock.calls.filter(([url]) => new URL(url).pathname === '/api/students/')).toHaveLength(1);
  });
  it('clears private views when a resource denial confirms the session expired', async () => {
    forgetSession(); let checks = 0;
    vi.stubGlobal('fetch', vi.fn(async url => {
      if (new URL(url).pathname === '/api/auth/me/' && ++checks === 1) return json(staff);
      return json({ detail: 'Authentication required.' }, 403);
    }));
    app('/portal/staff/students');
    await screen.findByText('Sign in page');
    expect(screen.queryByText('lecturer’s workspace')).toBeNull();
  });
});
