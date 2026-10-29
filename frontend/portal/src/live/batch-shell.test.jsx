import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../auth/context';
import LivePortal from './LivePortal';

vi.mock('./ForcedPasswordChange', () => ({ default: () => <main><h1>Choose a new password</h1></main> }));
vi.mock('./Courses', () => ({ default: () => <p>HOD course management</p> }));
vi.mock('./Teaching', () => ({ default: ({ section }) => <p>Teaching workspace: {section}</p> }));
vi.mock('./StudentRecordsBatch', () => ({ default: () => <p>Student approval workspace</p> }));
afterEach(cleanup);

function open(user, section = 'dashboard', role = user.role) {
  return render(<AuthContext.Provider value={{ user, status: 'ready', refreshUser: vi.fn(), signOut: vi.fn() }}>
    <MemoryRouter initialEntries={[`/portal/${role}/${section}`]}><Routes>
      <Route path="/portal/:role/:section?" element={<LivePortal />} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}
const student = { id: 11, username: 'synthetic-student', role: 'student', is_staff: false, permissions: [] };
const staff = { id: 12, username: 'synthetic-staff', role: 'staff', is_staff: true, permissions: [] };

describe('batch workspace integration', () => {
  it('blocks every workspace behind the mandatory password change, even a mismatched role URL', async () => {
    open({ ...student, must_change_password: true }, 'workflows', 'hod');
    await screen.findByRole('heading', { name: 'Choose a new password' });
    expect(screen.queryByRole('navigation')).toBeNull();
    expect(screen.queryByText('Student approval workspace')).toBeNull();
    expect(screen.queryByText(/Teaching workspace/)).toBeNull();
  });

  it('makes current message notifications usable from a student workspace', async () => {
    open(student, 'messages');
    await screen.findByText('Teaching workspace: messages');
    expect(screen.getByRole('link', { name: 'Messages' }).getAttribute('href')).toBe('/portal/student/messages');
    expect(screen.getByRole('link', { name: 'Earlier messages' })).toBeTruthy();
  });

  it('offers staff publishing and course workspaces without granting HOD administration', async () => {
    open(staff, 'timetable');
    await screen.findByText('Teaching workspace: timetable');
    expect(screen.getByRole('link', { name: 'Messages' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Course materials' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Guardian results' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Academic session' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Courses' })).toBeNull();
  });

  it('connects student documents and correction requests to their separate workspace', async () => {
    open(student, 'workflows');
    await screen.findByText('Student approval workspace');
    expect(screen.getByRole('link', { name: 'Documents and requests' }).getAttribute('aria-current')).toBe('page');
  });
  it('links HODs to course management and blocks the staff route', async () => {
    const hod = { ...staff, id: 1, role: 'hod', is_superuser: true };
    const view = open(hod, 'courses');
    await screen.findByText('HOD course management');
    expect(screen.getByRole('link', { name: 'Courses' }).getAttribute('aria-current')).toBe('page');
    view.unmount();
    open(staff, 'courses');
    expect(screen.getByText('This section is unavailable')).toBeTruthy();
    expect(screen.queryByText('HOD course management')).toBeNull();
  });

});
