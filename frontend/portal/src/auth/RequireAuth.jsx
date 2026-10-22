import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './useAuth';
import { hasPermission, workspaceRoles } from './permissions';

export default function RequireAuth({ children, staff = false, permission }) {
  const { user, status, error, refreshUser } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <main className="live-portal" role="status">Checking your session…</main>;
  if (status === 'error') return <main className="live-portal"><h1>Unable to check your session</h1><p role="alert">{error?.message || 'Check your connection and try again.'}</p><button onClick={() => { refreshUser().catch(() => {}); }}>Try again</button></main>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (!workspaceRoles(user).length || (staff && !user.is_staff) || (permission && !hasPermission(user, permission))) return <Navigate to="/access-denied" replace />;
  return <div key={user.id}>{children}</div>;
}
