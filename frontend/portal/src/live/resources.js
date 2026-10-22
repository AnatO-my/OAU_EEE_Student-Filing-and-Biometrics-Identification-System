import { useEffect, useState } from 'react';

// Abort on navigation and suppress late results, including servers that ignore abort.
export function useRemote(loader, dependencies) {
  const [state, setState] = useState({ data: null, error: '', loading: true });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    Promise.resolve().then(() => {
      if (alive) setState({ data: null, error: '', loading: true });
      if (!alive) throw new DOMException('Aborted', 'AbortError');
      return loader(controller.signal);
    }).then((data) => { if (alive) setState({ data, error: '', loading: false }); })
      .catch((error) => { if (alive && error.name !== 'AbortError') setState({ data: null, error: error.message, loading: false }); });
    return () => { alive = false; controller.abort(); };
    // Callers provide the complete resource key. The loader is intentionally not a key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, revision]);
  return { ...state, reload: () => setRevision((value) => value + 1) };
}

export const formatDate = (value) => value ? new Date(value).toLocaleString() : 'Not recorded';
export const hasPermission = (user, permission) => !!user?.is_staff && (user.is_superuser || user.permissions?.includes(permission));
export const isHod = (user) => user?.role === 'hod' && user.is_staff && user.is_superuser;
