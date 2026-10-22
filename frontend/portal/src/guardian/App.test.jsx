import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App, { BatchReview } from './App.jsx';
import { ApiError } from './api.js';

afterEach(cleanup);
const hod = { id: 1, username: 'hod', role: 'hod', is_staff: true, is_superuser: true };
const student = { student_id: 'student-1', full_name: 'Example Student', identifier_value: 'MOCK-001', current_level: 300 };
const preview = {
  id: 'batch-1', history_digest: 'reviewed-digest', queued_at: null, counts: { draft: 1 },
  preview: [{ student_id: student.student_id, name: student.full_name, identifier: 'MOCK-001', diagnostic_code: '',
    report: { text: 'Synthetic verified report' }, recipients: [{ guardian_id: 'guardian-1', guardian_name: 'Example Guardian', channel: 'email', destination: 'guardian@example.test', diagnostic_code: '' }] }],
  deliveries: [{ id: 1, channel: 'email', destination: 'guardian@example.test', status: 'draft', attempts: 0 }],
};
function client(overrides = {}) {
  return { me: vi.fn().mockResolvedValue(hod), sessions: vi.fn().mockResolvedValue([{ id: 1, name: '2026/2027' }]),
    students: vi.fn().mockResolvedValue({ results: [student], next: null }), preview: vi.fn().mockResolvedValue(preview),
    send: vi.fn().mockResolvedValue({ ...preview, queued_at: '2026-10-18T10:00:00Z', counts: { accepted: 1 }, deliveries: [{ ...preview.deliveries[0], status: 'accepted', attempts: 1 }] }),
    batch: vi.fn().mockResolvedValue(preview), logout: vi.fn().mockResolvedValue(null), ...overrides };
}

async function selectAndPreview(api) {
  render(<App api={api} />);
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Select Example Student' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Preview guardian emails' }).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Preview guardian emails' }));
  await screen.findByText('Report preview');
}

describe('HOD result-sharing page', () => {
  it('does not load private student or session data for a non-HOD account', async () => {
    const api = client({ me: vi.fn().mockResolvedValue({ role: 'staff', is_staff: true, is_superuser: false }) });
    render(<App api={api} />);
    await screen.findByText('HOD access required');
    expect(api.students).not.toHaveBeenCalled(); expect(api.sessions).not.toHaveBeenCalled();
  });

  it('requires review and queues the existing batch once without creating another preview', async () => {
    const api = client(); await selectAndPreview(api);
    expect(api.preview.mock.calls[0][0]).toMatchObject({ student_ids: ['student-1'], academic_session: 1, channels: ['email'] });
    expect(screen.getByRole('button', { name: 'Send 1 email' }).disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: /I have reviewed/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Send 1 email' }));
    await screen.findByText('The batch is queued. You can follow each email below.');
    expect(api.send).toHaveBeenCalledExactlyOnceWith(preview);
    expect(api.preview).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Send 1 email' })).toBeNull();
    expect(screen.getAllByText('Accepted by provider').length).toBeGreaterThan(0);
    expect(screen.getByText(/does not confirm that it reached/)).toBeTruthy();
  });

  it('reuses the same request UUID after an uncertain preview response', async () => {
    const api = client({ preview: vi.fn().mockRejectedValueOnce(new ApiError('Network interrupted')).mockResolvedValueOnce(preview) });
    render(<App api={api} />);
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Select Example Student' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Preview guardian emails' }).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Preview guardian emails' }));
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: 'Preview guardian emails' }));
    await screen.findByText('Report preview');
    expect(api.preview.mock.calls[0][0].request_id).toBe(api.preview.mock.calls[1][0].request_id);
  });

  it('does not automatically repeat an uncertain send', async () => {
    const api = client({ send: vi.fn().mockRejectedValue(new ApiError('Connection lost')) });
    await selectAndPreview(api);
    fireEvent.click(screen.getByRole('checkbox', { name: /I have reviewed/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Send 1 email' }));
    await screen.findByRole('alert');
    expect(api.send).toHaveBeenCalledTimes(1); expect(api.preview).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Keep this batch/)).toBeTruthy();
  });

  it('blocks preview-only batch delivery of non-email channels and displays uncertain outcomes', () => {
    render(<BatchReview batch={{ ...preview, counts: { draft: 1, unknown: 1 }, deliveries: [{ ...preview.deliveries[0], channel: 'whatsapp' }] }} busy={false} reviewed={true} setReviewed={vi.fn()} send={vi.fn()} refresh={vi.fn()} retry={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Send 1 email' }).disabled).toBe(true);
    expect(screen.getByText(/Some submissions have an uncertain outcome/)).toBeTruthy();
  });

  it('clears private workspace views on successful logout', async () => {
    const api = client(); await selectAndPreview(api);
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    await screen.findByText('Sign in to continue');
    expect(screen.queryByText('Example Guardian')).toBeNull();
  });

  it('loads saved batches from history without creating or sending another batch', async () => {
    const api = client({ history: vi.fn().mockResolvedValue({ next: null, results: [{ id: preview.id, academic_session: 1, semester: 'harmattan', created_at: '2026-10-18T10:00:00Z', queued_at: null, counts: { draft: 1 } }] }) });
    render(<App api={api} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Batch history', exact: true }));
    fireEvent.click(await screen.findByRole('button', { name: /2026\/2027 · harmattan/ }));
    await screen.findByText('Report preview');
    expect(api.batch).toHaveBeenCalledWith(preview.id);
    expect(api.preview).not.toHaveBeenCalled(); expect(api.send).not.toHaveBeenCalled();
  });
});
