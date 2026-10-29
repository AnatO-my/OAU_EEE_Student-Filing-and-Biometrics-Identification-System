import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Courses from './Courses';
import * as api from '../api';
vi.mock('../api', async () => ({ ...await vi.importActual('../api'), listCourses: vi.fn(), listCourseOfferings: vi.fn(), listAcademicSessions: vi.fn(), listGradingScales: vi.fn(), listManagedStaff: vi.fn(), createCourse: vi.fn(), createCourseOffering: vi.fn(), createAcademicSession: vi.fn(), apiRequest: vi.fn() }));
const hod = { id: 1, role: 'hod', is_staff: true, is_superuser: true };
const page = rows => ({ results: rows, next: null });
const offering = { id: 10, course: 2, academic_session: 3, semester: 'harmattan', level: 200, credit_units: 3, grading_scale: 4 };
function open(user = hod) { render(<MemoryRouter><Courses user={user} /></MemoryRouter>); }
afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
  api.listCourses.mockResolvedValue(page([{ id: 2, code: 'EEE201', title: 'Circuit theory' }]));
  api.listCourseOfferings.mockResolvedValue(page([offering]));
  api.listAcademicSessions.mockResolvedValue(page([{ id: 3, name: '2026/2027' }]));
  api.listGradingScales.mockResolvedValue(page([{ id: 4, name: 'Approved scale', is_published: true }, { id: 5, name: 'Unpublished scale', is_published: false }]));
  api.listManagedStaff.mockResolvedValue(page([{ id: 6, username: 'teacher', first_name: 'Course', last_name: 'Teacher', is_active: true }, { id: 7, username: 'inactive', is_active: false }]));
  api.apiRequest.mockResolvedValue(page([]));
});
it('creates a course and offers only published grading scales', async () => {
  open();
  await screen.findByText('Circuit theory', { selector: 'td' });
  expect(screen.queryByRole('option', { name: 'Unpublished scale' })).toBeNull();
  fireEvent.change(screen.getByLabelText('Course code'), { target: { value: 'EEE301' } });
  fireEvent.change(screen.getByLabelText('Course title'), { target: { value: 'Electronics' } });
  api.createCourse.mockResolvedValue({ id: 9, code: 'EEE301', title: 'Electronics' });
  fireEvent.click(screen.getByRole('button', { name: 'Create course' }));
  await screen.findByText('Course created. You can now add its semester offering.');
  expect(api.createCourse).toHaveBeenCalledWith('EEE301', 'Electronics');
});
it('creates a semester offering with numeric IDs and credit units', async () => {
  open(); await screen.findByText('Circuit theory', { selector: 'td' });
  for (const [label, value] of [['Catalogue course', '2'], ['Offering academic session', '3'], ['Semester', 'rain'], ['Level', '200'], ['Credit units', '3'], ['Published grading scale', '4']]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  api.createCourseOffering.mockResolvedValue({ ...offering, semester: 'rain' });
  fireEvent.click(screen.getByRole('button', { name: 'Create semester offering' }));
  await screen.findByText('Semester offering created. Assign its teaching staff below.');
  expect(api.createCourseOffering).toHaveBeenCalledWith({ course: 2, academic_session: 3, semester: 'rain', level: 200, credit_units: 3, grading_scale: 4 });
});
it('shows server duplicate errors and preserves the draft', async () => {
  open(); await screen.findByText('Circuit theory', { selector: 'td' });
  fireEvent.change(screen.getByLabelText('Course code'), { target: { value: 'EEE201' } });
  fireEvent.change(screen.getByLabelText('Course title'), { target: { value: 'Existing course' } });
  api.createCourse.mockRejectedValue({ message: 'Course code already exists.', status: 400 });
  fireEvent.click(screen.getByRole('button', { name: 'Create course' }));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Course code already exists.');
  expect(screen.getByLabelText('Course title').value).toBe('Existing course');
});
it('loads every course page and shows a later-page course in the offering selector', async () => {
  api.listCourses.mockImplementation(pageNumber => Promise.resolve(pageNumber === 1 ? { results: [{ id: 2, code: 'EEE201', title: 'Circuit theory' }], next: '/api/courses/?page=2' } : page([{ id: 12, code: 'EEE401', title: 'Control' }])));
  open();
  expect(await screen.findByRole('option', { name: 'EEE401 · Control' })).toBeTruthy();
  expect(api.listCourses.mock.calls.some(([number]) => number === 2)).toBe(true);
});
it('activates staff assignments through the existing endpoint and can deactivate an existing assignment', async () => {
  api.apiRequest.mockImplementation((path, options) => Promise.resolve(options?.method === 'PUT' ? { id: 20, staff: 6, is_active: options.body.is_active } : page([{ id: 20, staff: 6, staff_username: 'teacher', staff_name: 'Course Teacher', staff_is_active: true, is_active: true }])));
  open(); await screen.findByText('Circuit theory', { selector: 'td' });
  fireEvent.change(screen.getByLabelText('Offering to manage'), { target: { value: '10' } });
  await screen.findByRole('button', { name: 'Deactivate assignment' });
  expect(screen.queryByRole('option', { name: 'inactive (inactive)' })).toBeNull();
  fireEvent.change(screen.getByLabelText('Teaching staff'), { target: { value: '6' } });
  fireEvent.click(screen.getByLabelText('Confirm this staff member should teach this offering'));
  fireEvent.click(screen.getByRole('button', { name: 'Assign teaching staff' }));
  await screen.findByText('Teaching assignment activated.');
  expect(api.apiRequest).toHaveBeenCalledWith('/api/attendance/offerings/10/staff/', { method: 'PUT', body: { staff: 6, is_active: true } });
  await screen.findByRole('button', { name: 'Deactivate assignment' });
  fireEvent.click(screen.getByLabelText('Confirm assignment change'));
  fireEvent.click(screen.getByRole('button', { name: 'Deactivate assignment' }));
  await screen.findByText('Teaching assignment deactivated.');
  expect(api.apiRequest).toHaveBeenCalledWith('/api/attendance/offerings/10/staff/', { method: 'PUT', body: { staff: 6, is_active: false } });
});
it('does not request HOD resources for ordinary staff', () => {
  open({ role: 'staff', is_staff: true, is_superuser: false });
  expect(screen.getByText('HOD access required')).toBeTruthy();
  expect(api.listCourses).not.toHaveBeenCalled();
});
it('creates an academic session without silently selecting it as current', async () => {
  open(); await screen.findByText('Circuit theory', { selector: 'td' });
  fireEvent.change(screen.getByLabelText('New academic session'), { target: { value: '2027/2028' } });
  api.createAcademicSession.mockResolvedValue({ id: 8, name: '2027/2028' });
  fireEvent.click(screen.getByRole('button', { name: 'Create academic session' }));
  await screen.findByText('Academic session created; the current session was not changed.');
  expect(api.createAcademicSession).toHaveBeenCalledWith('2027/2028');
  await waitFor(() => expect(api.listAcademicSessions.mock.calls.length).toBeGreaterThan(1));
});
