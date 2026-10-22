import { useMemo } from 'react';
import { Workspace } from '../../../guardian-results/src/App.jsx';
import { apiRequest, collectPages } from '../api';
import './guardian-scoped.css';

// Reuse the tested review/consent/stable-batch workflow, with the portal's single
// session lifecycle. No credentials, contacts or reports go to browser storage.
export default function GuardianResults() {
  const api = useMemo(() => {
    const request = (path, options) => apiRequest(path, options);
    const id = encodeURIComponent;
    return {
      request,
      sessions: () => collectPages((page) => request(`/api/academic-sessions/?page=${page}`)),
      students: (params) => request(`/api/students/?${new URLSearchParams(params)}`),
      guardians: (student) => collectPages((page) => request(`/api/students/${id(student)}/guardians/?page=${page}`)),
      preference: (student, guardian) => request(`/api/students/${id(student)}/guardians/${id(guardian)}/result-sharing/`),
      savePreference: (student, guardian, body) => request(`/api/students/${id(student)}/guardians/${id(guardian)}/result-sharing/`, { method: 'PUT', body }),
      preview: (body) => request('/api/result-shares/preview/', { method: 'POST', body }),
      batch: (batch) => request(`/api/result-shares/${id(batch)}/`),
      send: (batch) => request(`/api/result-shares/${id(batch.id)}/send/`, { method: 'POST', body: { expected_digest: batch.history_digest } }),
      retry: (batch) => request(`/api/result-shares/${id(batch)}/retry/`, { method: 'POST', body: {} }),
      history: (page = 1) => request(`/api/result-shares/?page=${page}`),
    };
  }, []);
  return <div className="guardian-workspace"><Workspace api={api} /></div>;
}
