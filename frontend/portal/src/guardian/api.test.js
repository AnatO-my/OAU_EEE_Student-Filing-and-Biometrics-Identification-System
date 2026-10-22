import { describe, expect, it, vi } from 'vitest';
import { ApiError, createApi } from './api.js';

const ok = (data, status = 200) => ({ ok: true, status, json: async () => data });
const failed = (data, status) => ({ ok: false, status, json: async () => data });

describe('same-origin result-sharing API client', () => {
  it('refreshes CSRF after login and never stores credentials in browser storage', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(ok({ csrfToken: 'before' }))
      .mockResolvedValueOnce(ok({ role: 'hod' })).mockResolvedValueOnce(ok({ csrfToken: 'after' }))
      .mockResolvedValueOnce(ok({ id: 'batch' }));
    const api = createApi({ fetchImpl });
    await api.login('hod', 'synthetic-password');
    await api.preview({ request_id: 'stable-id', channels: ['email'] });
    expect(fetchImpl.mock.calls[1][1].headers['X-CSRFToken']).toBe('before');
    expect(fetchImpl.mock.calls[3][1].headers['X-CSRFToken']).toBe('after');
    for (const [, options] of fetchImpl.mock.calls) {
      expect(options.credentials).toBe('same-origin');
      expect(options.cache).toBe('no-store');
    }
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('sends the reviewed digest and never automatically retries a write', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(ok({ csrfToken: 'token' }))
      .mockRejectedValueOnce(new TypeError('network failure'));
    const api = createApi({ fetchImpl });
    await expect(api.send({ id: 'batch-id', history_digest: 'reviewed-digest' })).rejects.toBeInstanceOf(ApiError);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetchImpl.mock.calls[1][1].body)).toEqual({ expected_digest: 'reviewed-digest' });
  });

  it('revokes in-memory session state on loss of authorization', async () => {
    const onSessionLost = vi.fn();
    const fetchImpl = vi.fn().mockResolvedValue(failed({ detail: 'Session expired' }, 403));
    const api = createApi({ fetchImpl, onSessionLost });
    await expect(api.batch('batch')).rejects.toMatchObject({ status: 403 });
    expect(onSessionLost).toHaveBeenCalledOnce();
  });

  it('rejects late responses from a previous session', async () => {
    let resolve;
    const api = createApi({ fetchImpl: () => new Promise((done) => { resolve = done; }) });
    const pending = api.me();
    api.forget(); resolve(ok({ role: 'hod' }));
    await expect(pending).rejects.toMatchObject({ status: 401 });
  });

  it('does not follow server pagination to arbitrary origins', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(ok({ results: [{ id: 1 }], next: 'https://elsewhere.invalid/' }))
      .mockResolvedValueOnce(ok({ results: [{ id: 2 }], next: null }));
    expect(await createApi({ fetchImpl }).sessions()).toEqual([{ id: 1 }, { id: 2 }]);
    expect(fetchImpl.mock.calls.map(([path]) => path)).toEqual(['/api/academic-sessions/?page=1', '/api/academic-sessions/?page=2']);
  });

  it('retains API validation messages without displaying raw HTML responses', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(failed({ student_ids: ['Duplicate entries are not allowed.'] }, 400));
    await expect(createApi({ fetchImpl }).me()).rejects.toThrow('Duplicate entries are not allowed.');
    const malformed = createApi({ fetchImpl: vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => { throw new Error('<html>'); } }) });
    await expect(malformed.me()).rejects.toThrow('unreadable response');
  });
});
