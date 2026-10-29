// Only department message links can supply a post-login destination.
export function messageReturnPath(role, value) {
  if (!['student', 'staff', 'hod'].includes(role) || typeof value !== 'string') return null;
  let target;
  try { target = new URL(value, window.location.origin); } catch { return null; }
  if (target.origin !== window.location.origin) return null;
  const isGeneric = target.pathname === '/portal' && target.searchParams.get('section') === 'messages';
  const isWorkspace = /^\/portal\/(student|staff|hod)\/messages$/.test(target.pathname);
  if (!isGeneric && !isWorkspace) return null;
  const id = target.searchParams.get('message');
  const validId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id || '');
  return `/portal/${role}/messages${validId ? `?message=${encodeURIComponent(id)}` : ''}`;
}
