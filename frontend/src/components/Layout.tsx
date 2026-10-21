import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';

const LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/services', label: 'Services' },
  { to: '/about', label: 'About' },
  { to: '/contact', label: 'Contact' },
];

function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const cls = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined);

  // Admins see only the Admin link (+ Logout) — nothing customer-facing.
  if (user?.is_admin) {
    return (
      <nav className="navbar">
        <Link to="/admin" className="logo">Drovery</Link>
        <ul>
          <li><NavLink to="/admin" className={cls}>Admin</NavLink></li>
          <li>
            <a
              href="/login"
              className="nav-cta"
              onClick={(e) => {
                e.preventDefault();
                logout();
                navigate('/login');
              }}
            >
              Logout
            </a>
          </li>
        </ul>
      </nav>
    );
  }

  const links = user && pathname.startsWith('/profile')
    ? [LINKS[0]!, LINKS[1]!, { to: '/order', label: 'New Order' }]
    : LINKS;

  return (
    <nav className="navbar">
      <Link to="/" className="logo">Drovery</Link>
      <ul>
        {links.map((l) => (
          <li key={l.to}>
            <NavLink to={l.to} end={'end' in l ? l.end : undefined} className={cls}>{l.label}</NavLink>
          </li>
        ))}
        <li>
          {user ? (
            <Link to="/profile" className="nav-cta">👤 {user.first_name}</Link>
          ) : pathname === '/login' ? (
            <Link to="/signup" className="nav-cta">Sign Up</Link>
          ) : (
            <Link to="/login" className="nav-cta">Login</Link>
          )}
        </li>
      </ul>
    </nav>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  return (
    <>
      <Navbar />
      <Outlet />
      <footer className="footer">
        {pathname === '/' ? (
          <>
            © 2026 Drovery. All rights reserved. &nbsp;|&nbsp; <Link to="/about">About</Link> &nbsp;|&nbsp;{' '}
            <Link to="/contact">Contact</Link>
          </>
        ) : pathname.startsWith('/admin') ? (
          '© 2026 Drovery. Admin panel.'
        ) : (
          '© 2026 Drovery. All rights reserved.'
        )}
      </footer>
    </>
  );
}
