import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiRequest, changePassword, forgetSession, importPendingCaptures, login, previewPendingCaptures, subscribeSessionCheck, uploadStudentDocument } from './api';

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(forgetSession);

describe('Django transport', () => {
  it('preserves raw bytes and the preview hash for capture preview/import', async () => {
    const fetch = vi.fn().mockImplementation(async () => json({ csrfToken: 'csrf-a' }));
    vi.stubGlobal('fetch', fetch);
    const bytes = new Uint8Array([123, 125, 13, 10]).buffer;
    await previewPendingCaptures('class-a', bytes);
    await importPendingCaptures('class-a', bytes, 'a'.repeat(64));
    const writes = fetch.mock.calls.filter(([, options]) => options.method === 'POST');
    expect(writes).toHaveLength(2);
    for (const [, options] of writes) {
      expect(options.body).toBe(bytes);
      expect(options.headers['Content-Type']).toBe('application/x-ndjson');
      expect(options.headers['X-CSRFToken']).toBe('csrf-a');
      expect(options.credentials).toBe('same-origin');
    }
    expect(writes[1][1].headers['X-Capture-SHA256']).toBe('a'.repeat(64));
  });

  it('leaves multipart boundaries to the browser for document uploads', async () => {
    const fetch = vi.fn().mockImplementation(async () => json({ csrfToken: 'csrf-a' }));
    vi.stubGlobal('fetch', fetch);
    await uploadStudentDocument('student-a', new File(['%PDF-'], 'review.pdf'), 'result');
    const options = fetch.mock.calls.at(-1)[1];
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.body.get('document_type')).toBe('result');
    expect(options.headers['Content-Type']).toBeUndefined();
  });

  it('uses the rotated CSRF token after login', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json({ csrfToken: 'before' }))
      .mockResolvedValueOnce(json({ id: 1, role: 'staff' }))
      .mockResolvedValueOnce(json({ csrfToken: 'after' }))
      .mockResolvedValueOnce(json({ detail: 'Password changed.' }));
    vi.stubGlobal('fetch', fetch);
    await login('staff', 'synthetic');
    await changePassword('synthetic', 'synthetic-new');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ username: 'staff', password: 'synthetic' });
    expect(fetch.mock.calls[3][1].headers['X-CSRFToken']).toBe('after');
  });

  it('rejects old responses after a session changes', async () => {
    let finish;
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(resolve => { finish = resolve; })));
    const pending = apiRequest('/api/students/');
    forgetSession();
    finish(json({ results: [{ full_name: 'Previous user record' }] }));
    await expect(pending).rejects.toMatchObject({ status: 401 });
  });

  it('requests identity verification after a denied resource without retrying it', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ detail: 'Permission denied.' }, 403));
    vi.stubGlobal('fetch', fetch);
    const listener = vi.fn();
    const unsubscribe = subscribeSessionCheck(listener);
    try { await expect(apiRequest('/api/students/')).rejects.toMatchObject({ status: 403 }); }
    finally { unsubscribe(); }
    expect(listener).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('rejects mixed body encodings and non-API paths', async () => {
    await expect(apiRequest('/api/results/', { body: {}, rawBody: 'data' })).rejects.toBeInstanceOf(TypeError);
    await expect(apiRequest('https://example.invalid/api/students/')).rejects.toBeInstanceOf(TypeError);
  });
  it('also verifies the session after password-change access expires', async () => {
    const fetch = vi.fn(async url => new URL(url).pathname.endsWith('/csrf/') ? json({ csrfToken: 'token' }) : json({ detail: 'Authentication required.' }, 403));
    vi.stubGlobal('fetch', fetch);
    const listener = vi.fn(); const unsubscribe = subscribeSessionCheck(listener);
    try { await expect(changePassword('old', 'new')).rejects.toMatchObject({ status: 403 }); }
    finally { unsubscribe(); }
    expect(listener).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(3);
  });
});
