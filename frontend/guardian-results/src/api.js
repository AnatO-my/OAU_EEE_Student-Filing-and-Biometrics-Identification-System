// Session cookies stay in the browser. Tokens and reports remain in memory only.
export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; }
}

function detail(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(detail).join(' ');
  if (value && typeof value === 'object') {
    if (value.detail) return detail(value.detail);
    return Object.entries(value).map(([key, item]) => `${key.replaceAll('_', ' ')}: ${detail(item)}`).join(' ');
  }
  return 'The request could not be completed.';
}

export function createApi({ fetchImpl = (...args) => fetch(...args), onSessionLost = () => {} } = {}) {
  let csrfToken = null;
  let epoch = 0;

  async function request(path, { method = 'GET', body } = {}) {
    if (!path.startsWith('/api/') || path.startsWith('//') || path.includes('://')) {
      throw new ApiError('Unsupported API path.');
    }
    const started = epoch;
    const headers = { Accept: 'application/json' };
    if (method !== 'GET') {
      if (!csrfToken) await csrf();
      headers['X-CSRFToken'] = csrfToken;
      headers['Content-Type'] = 'application/json';
    }
    let response;
    try {
      response = await fetchImpl(path, {
        method, headers, credentials: 'same-origin', cache: 'no-store',
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      throw new ApiError('Unable to reach the server. Check the connection and try again.');
    }
    if (started !== epoch) throw new ApiError('The session changed. Sign in again.', 401);
    let data = null;
    try { if (response.status !== 204) data = await response.json(); } catch { /* no raw HTML in errors */ }
    if (!response.ok) {
      if ([401, 403].includes(response.status) && !path.startsWith('/api/auth/login/')) {
        csrfToken = null;
        epoch += 1;
        onSessionLost();
      }
      throw new ApiError(data ? detail(data) : 'The server could not complete this request.', response.status);
    }
    if (response.status !== 204 && data === null) throw new ApiError('The server returned an unreadable response. Refresh the current status before retrying.');
    return data;
  }

  async function csrf() {
    const data = await request('/api/auth/csrf/');
    if (!data?.csrfToken) throw new ApiError('Unable to obtain a secure session token.');
    csrfToken = data.csrfToken;
  }

  async function catalog(path) {
    const rows = [];
    for (let page = 1; page <= 100; page += 1) {
      const data = await request(`${path}?page=${page}`);
      rows.push(...data.results);
      if (!data.next) return rows;
    }
    throw new ApiError('Too many catalog pages. Contact the department administrator.');
  }

  return {
    request,
    forget() { csrfToken = null; epoch += 1; },
    me: () => request('/api/auth/me/'),
    async login(username, password) {
      await csrf();
      const user = await request('/api/auth/login/', { method: 'POST', body: { username, password } });
      csrfToken = null;
      await csrf(); // Django rotates the CSRF token on login.
      return user;
    },
    async logout() {
      await request('/api/auth/logout/', { method: 'POST' });
      csrfToken = null; epoch += 1;
    },
    sessions: () => catalog('/api/academic-sessions/'),
    students: (params) => request(`/api/students/?${new URLSearchParams(params)}`),
    guardians: (studentId) => catalog(`/api/students/${encodeURIComponent(studentId)}/guardians/`),
    preference: (studentId, guardianId) => request(`/api/students/${encodeURIComponent(studentId)}/guardians/${encodeURIComponent(guardianId)}/result-sharing/`),
    savePreference: (studentId, guardianId, body) => request(`/api/students/${encodeURIComponent(studentId)}/guardians/${encodeURIComponent(guardianId)}/result-sharing/`, { method: 'PUT', body }),
    preview: (body) => request('/api/result-shares/preview/', { method: 'POST', body }),
    batch: (id) => request(`/api/result-shares/${encodeURIComponent(id)}/`),
    send: (batch) => request(`/api/result-shares/${encodeURIComponent(batch.id)}/send/`, { method: 'POST', body: { expected_digest: batch.history_digest } }),
    retry: (id) => request(`/api/result-shares/${encodeURIComponent(id)}/retry/`, { method: 'POST', body: {} }),
    history: (page = 1) => request(`/api/result-shares/?page=${page}`),
  };
}
