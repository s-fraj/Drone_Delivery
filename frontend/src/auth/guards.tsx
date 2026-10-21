import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

function Splash() {
  return <div style={{ padding: '8rem 1rem', textAlign: 'center', color: 'var(--muted)' }}>Loading…</div>;
}

/** Any signed-in user. Admins are bounced to the admin dashboard. */
export function RequireAuth({ allowAdmin = false }: { allowAdmin?: boolean }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Splash />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.is_admin && !allowAdmin) return <Navigate to="/admin" replace />;
  return <Outlet />;
}

/** Admin-only. Non-admins go back to their profile. */
export function RequireAdmin() {
  const { user, loading } = useAuth();
  if (loading) return <Splash />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) return <Navigate to="/profile" replace />;
  return <Outlet />;
}

/** Login/signup pages: skip them when already signed in. */
export function RedirectIfAuthed() {
  const { user, loading } = useAuth();
  if (loading) return <Splash />;
  if (user) return <Navigate to={user.is_admin ? '/admin' : '/profile'} replace />;
  return <Outlet />;
}
