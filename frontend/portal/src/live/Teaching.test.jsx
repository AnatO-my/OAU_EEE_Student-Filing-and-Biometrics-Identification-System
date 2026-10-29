import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Teaching from './Teaching';
import { StudentEligibility, MeetingReview } from './AttendancePolicy';
import { apiRequest } from '../api';
vi.mock('../api', () => ({ apiRequest: vi.fn() }));
afterEach(() => { cleanup(); window.history.replaceState({}, '', '/'); });
beforeEach(() => vi.clearAllMocks());
const student = { role: 'student', is_staff: false };
const staff = { role: 'staff', is_staff: true, permissions: ['teaching.publish_message'] };
const message = { id: 'message-one', version: 1, subject: 'Notice', body: 'Website-only body', withdrawn: false, is_sender: false, read_at: null };
it('highlights an email-linked message but does not mark it read before deliberate open', async () => {
  window.history.replaceState({}, '', '/portal?section=messages&message=message-one');
  apiRequest.mockImplementation(path => Promise.resolve(path.endsWith('/courses/') ? [] : path.endsWith('/messages/') ? [message] : message));
  render(<Teaching user={student} section="messages" />);
  await screen.findByText('Notice · Linked message');
  expect(apiRequest.mock.calls.some(([path]) => path.endsWith('/messages/message-one/'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Open message' }));
  await screen.findByText('Website-only body');
  expect(apiRequest.mock.calls.filter(([path]) => path.endsWith('/messages/message-one/'))).toHaveLength(1);
});
it('offers human recipient names and publishes their internal identifiers without approval', async () => {
  apiRequest.mockImplementation((path, options) => Promise.resolve(path.endsWith('/courses/') ? [] : path.endsWith('/audience-options/') ? { students: [{ id: 'student-uuid', user_id: 12, full_name: 'Sample Student', identifier_value: 'EEE/001' }], staff: [{ id: 8, full_name: 'Course Teacher' }] } : options?.method === 'POST' ? { ...message, is_sender: true, audience: options.body.audience, read_count: 0, recipient_count: 1 } : []));
  render(<Teaching user={staff} section="messages" />);
  const option = await screen.findByRole('option', { name: 'Sample Student · EEE/001' });
  expect(screen.getByRole('option', { name: 'Course Teacher' })).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Course announcement' } });
  fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'A new website announcement.' } });
  option.selected = true;
  fireEvent.change(option.parentElement);
  fireEvent.click(screen.getByRole('button', { name: 'Publish and queue link notifications' }));
  await waitFor(() => expect(apiRequest.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true));
  const [, options] = apiRequest.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(options.body.audience.student_ids).toEqual(['student-uuid']);
  expect(options.body.body).toBe('A new website announcement.');
});
it('keeps no-finalised-data exam eligibility visibly unknown for the student', async () => {
  apiRequest.mockResolvedValue([{ offering_id: 3, course: 'EEE301', rate_percent: null, pending_meetings: 2, excused_meetings: 0, exam_status: 'unknown' }]);
  const { container } = render(<StudentEligibility />);
  const details = container.querySelector('details'); details.open = true; fireEvent(details, new Event('toggle'));
  await screen.findByText('EEE301');
  expect(screen.getByText('Unknown')).toBeTruthy();
  expect(screen.getByText('unknown')).toBeTruthy();
});

it('lets staff explicitly flag an unselected live capture instead of silently treating it as deferred', async () => {
  const actor = { is_staff: true, permissions: ['attendance.correct_attendance', 'attendance.import_pending_captures'] };
  apiRequest.mockImplementation((path, options) => Promise.resolve(options?.method === 'POST' ? {} : path.endsWith('/captures/') ? { results: [{ capture_id: 'capture-one', state: 'archived', mode: 'deferred', review_selected: false }], next: null } : { collection_status: 'open', finalised: false, revision: 0, confirmed_records: [], confirmed_excusals: [] }));
  const { container } = render(<MeetingReview user={actor} session={{ id: 'meeting-one', status: 'open', student_ids: [], student_details: [], current_roster_students: [] }} />);
  const details = container.querySelector('details'); details.open = true; fireEvent(details, new Event('toggle'));
  const choice = await screen.findByLabelText('Review context');
  fireEvent.change(choice, { target: { value: 'live' } });
  fireEvent.click(screen.getByRole('button', { name: 'Choose for staff review' }));
  await waitFor(() => expect(apiRequest.mock.calls.some(([path, options]) => path.endsWith('/captures/capture-one/review/') && options?.body.mode === 'live')).toBe(true));
});


it('focuses an explicitly opened reader, updates read state and closes back to the inbox', async () => {
  let opened = false;
  const read = { ...message, read_at: '2026-10-26T10:00:00Z' };
  apiRequest.mockImplementation(async path => {
    if (path.endsWith('/courses/')) return [];
    if (path.endsWith('/messages/')) return [opened ? read : message];
    opened = true; return read;
  });
  render(<Teaching user={student} section="messages" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Open message' }));
  const heading = await screen.findByRole('heading', { name: 'Notice · Version 1' });
  await waitFor(() => expect(document.activeElement).toBe(heading));
  expect(screen.getByText(/Read on website:/)).toBeTruthy();
  await screen.findByRole('cell', { name: 'Read' });
  fireEvent.click(screen.getByRole('button', { name: 'Close message' }));
  expect(screen.queryByText('Website-only body')).toBeNull();
  expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Department messages' }));
});
it('keeps receipt counts visible for an author who is also a recipient', async () => {
  apiRequest.mockImplementation(async path => path.endsWith('/courses/') ? [] : path.endsWith('/audience-options/') ? { students: [], staff: [] } : [{ ...message, is_sender: true, read_at: '2026-10-26T10:00:00Z', read_count: 1, recipient_count: 3 }]);
  render(<Teaching user={staff} section="messages" />);
  await screen.findByRole('cell', { name: '1/3 recipients read' });
});
it('removes old reader content on refresh and requires deliberate opening of a revised version', async () => {
  let version = 1;
  apiRequest.mockImplementation(async path => path.endsWith('/courses/') ? [] : path.endsWith('/messages/') ? [{ ...message, version }] : { ...message, version, body: version === 1 ? 'Original body' : 'Revised body' });
  render(<Teaching user={student} section="messages" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Open message' }));
  await screen.findByText('Original body');
  version = 2;
  fireEvent.click(screen.getByRole('button', { name: 'Refresh messages' }));
  await screen.findByRole('cell', { name: '2' });
  expect(screen.queryByText('Original body')).toBeNull();
  expect(screen.queryByText('Revised body')).toBeNull();
  expect(apiRequest.mock.calls.filter(([path]) => path.endsWith('/messages/message-one/'))).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Open message' }));
  await screen.findByText('Revised body');
});
it('does not present stale message content when opening another message fails', async () => {
  apiRequest.mockImplementation(async path => {
    if (path.endsWith('/courses/')) return [];
    if (path.endsWith('/messages/')) return [message, { ...message, id: 'message-two', subject: 'Second notice' }];
    if (path.endsWith('/message-two/')) throw new Error('Message unavailable.');
    return message;
  });
  render(<Teaching user={student} section="messages" />);
  fireEvent.click((await screen.findAllByRole('button', { name: 'Open message' }))[0]);
  await screen.findByText('Website-only body');
  fireEvent.click(screen.getAllByRole('button', { name: 'Open message' })[1]);
  await screen.findByRole('alert');
  expect(screen.queryByText('Website-only body')).toBeNull();
});
it('shows retained message bodies only through the author history view', async () => {
  const own = { ...message, is_sender: true, audience: {}, read_count: 1, recipient_count: 1 };
  apiRequest.mockImplementation(async path => path.endsWith('/courses/') ? [] : path.endsWith('/audience-options/') ? { students: [], staff: [] } : path.endsWith('/history/') ? [{ ...own, body: 'Retained original text', receipts: [{ recipient_id: 10, read_at: null }] }] : path.endsWith('/messages/') ? [own] : own);
  render(<Teaching user={staff} section="messages" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Open message' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Review versions and recipient reads' }));
  await screen.findByText('Retained original text');
});
