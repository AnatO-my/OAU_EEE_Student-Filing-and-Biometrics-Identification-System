import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Teaching from './Teaching';
import { apiRequest } from '../api';

vi.mock('../api', () => ({ apiRequest: vi.fn() }));
const staff = { is_staff: true, permissions: ['teaching.manage_material'] };
const student = { is_staff: false, role: 'student' };
const offering = { id: 4, course: 'EEE301', session: '2026/2027', semester: 'harmattan' };
const material = { id: 'material-one', offering: 4, title: 'Circuit notes', version: 1,
  filename: 'notes.pdf', withdrawn: false, download_url: '/api/teaching/materials/material-one/versions/1/download/' };
beforeEach(() => { vi.clearAllMocks(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function fields() {
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: '4' } });
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Circuit notes' } });
  fireEvent.change(screen.getByLabelText('Written reason'), { target: { value: 'Lecture resource' } });
  fireEvent.change(screen.getByLabelText('Material file'), { target: { files: [new File(['%PDF-1.4'], 'notes.pdf', { type: 'application/pdf' })] } });
}
it('submits the selected offering as multipart, confirms success and resets the upload form', async () => {
  let rows = [];
  apiRequest.mockImplementation(async (path, options = {}) => {
    if (options.method === 'POST') { rows = [material]; return material; }
    return path.endsWith('/courses/') ? [offering] : rows;
  });
  render(<Teaching user={staff} section="materials" />);
  await screen.findByRole('option', { name: /EEE301/ });
  fields();
  fireEvent.submit(screen.getByLabelText('Title').closest('form'));
  await screen.findByText('Material uploaded successfully.');
  const [path, options] = apiRequest.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(path).toBe('/api/teaching/materials/');
  expect(options.rawBody).toBeInstanceOf(FormData);
  expect(options.rawBody.get('offering')).toBe('4');
  expect(options.rawBody.get('title')).toBe('Circuit notes');
  expect(options.rawBody.get('expected_version')).toBe('0');
  expect(options.rawBody.get('withdrawn')).toBe('false');
  expect(options.rawBody.get('event_id')).toBeTruthy();
  expect(screen.getByLabelText('Title').value).toBe('');
  expect(screen.getByLabelText('Course').value).toBe('');
  await screen.findByRole('cell', { name: 'Circuit notes' });
});
it('explains unavailable offerings and refreshes the selector after course assignment', async () => {
  let courses = [];
  apiRequest.mockImplementation(async path => path.endsWith('/courses/') ? courses : []);
  render(<Teaching user={staff} section="materials" />);
  await screen.findByText(/No course offerings are available/);
  expect(screen.getByRole('button', { name: 'Save material version' }).disabled).toBe(true);
  courses = [offering];
  fireEvent.click(screen.getByRole('button', { name: 'Refresh materials' }));
  await screen.findByRole('option', { name: /EEE301/ });
  expect(screen.getByRole('button', { name: 'Save material version' }).disabled).toBe(false);
});
it('shows a failed upload without discarding input and reuses its event on an exact retry', async () => {
  let failed = false;
  apiRequest.mockImplementation(async (path, options = {}) => {
    if (options.method === 'POST') { if (!failed) { failed = true; throw new Error('Unable to reach the server.'); } return material; }
    return path.endsWith('/courses/') ? [offering] : [];
  });
  render(<Teaching user={staff} section="materials" />);
  await screen.findByRole('option', { name: /EEE301/ });
  fields();
  const form = screen.getByLabelText('Title').closest('form');
  fireEvent.submit(form);
  await screen.findByRole('alert');
  expect(screen.queryByText('Material uploaded successfully.')).toBeNull();
  expect(screen.getByLabelText('Title').value).toBe('Circuit notes');
  fireEvent.submit(form);
  await screen.findByText('Material uploaded successfully.');
  const writes = apiRequest.mock.calls.filter(([, options]) => options?.method === 'POST');
  expect(writes).toHaveLength(2);
  expect(writes[0][1].rawBody.get('event_id')).toBe(writes[1][1].rawBody.get('event_id'));
});
it('offers students downloads without upload or staff archive controls', async () => {
  const objectUrl = vi.fn().mockReturnValue('blob:synthetic-material');
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: objectUrl });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  apiRequest.mockImplementation(async (path, options = {}) => options.responseType === 'blob' ? new Blob(['%PDF-1.4']) : path.endsWith('/courses/') ? [offering] : [material]);
  render(<Teaching user={student} section="materials" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Download' }));
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(apiRequest).toHaveBeenCalledWith(material.download_url, { responseType: 'blob' });
  expect(screen.queryByLabelText('Material file')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Version archive' })).toBeNull();
});
it('sends replacement and withdrawal to the existing material with the displayed version', async () => {
  apiRequest.mockImplementation(async (path, options = {}) => options.method === 'PUT' ? { ...material, version: 2 } : path.endsWith('/courses/') ? [offering] : [material]);
  render(<Teaching user={staff} section="materials" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Replace' }));
  fireEvent.change(screen.getByLabelText('Written reason'), { target: { value: 'Corrected notes' } });
  fireEvent.submit(screen.getByLabelText('Material file').closest('form'));
  await screen.findByText('Material replacement saved successfully.');
  let write = apiRequest.mock.calls.find(([, options]) => options?.method === 'PUT');
  expect(write[0]).toBe('/api/teaching/materials/material-one/');
  expect(write[1].rawBody.get('expected_version')).toBe('1');
  expect(write[1].rawBody.get('offering')).toBe('4');
  fireEvent.change(screen.getByPlaceholderText('Written withdrawal reason'), { target: { value: 'Withdraw obsolete notes' } });
  fireEvent.click(screen.getByLabelText('Confirm withdrawal'));
  fireEvent.submit(screen.getByPlaceholderText('Written withdrawal reason').closest('form'));
  await screen.findByText('Material withdrawn successfully.');
  write = apiRequest.mock.calls.filter(([, options]) => options?.method === 'PUT').at(-1);
  expect(write[1].rawBody.get('withdrawn')).toBe('true');
  expect(write[1].rawBody.get('title')).toBe('Circuit notes');
});
