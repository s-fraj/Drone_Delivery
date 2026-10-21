import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { RedirectIfAuthed, RequireAdmin, RequireAuth } from '@/auth/guards';
import Home from '@/pages/Home';
import Services from '@/pages/Services';
import About from '@/pages/About';
import Contact from '@/pages/Contact';
import Login from '@/pages/Login';
import Signup from '@/pages/Signup';
import NotFound from '@/pages/NotFound';

// Map-heavy pages are code-split so Leaflet isn't in the marketing-page bundle.
const Order = lazy(() => import('@/pages/Order'));
const Profile = lazy(() => import('@/pages/Profile'));
const Admin = lazy(() => import('@/pages/Admin'));

const Fallback = () => <div style={{ padding: '8rem 1rem', textAlign: 'center', color: 'var(--muted)' }}>Loading…</div>;

export default function App() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="services" element={<Services />} />
          <Route path="about" element={<About />} />
          <Route path="contact" element={<Contact />} />

          <Route element={<RedirectIfAuthed />}>
            <Route path="login" element={<Login />} />
            <Route path="signup" element={<Signup />} />
          </Route>

          <Route element={<RequireAuth />}>
            <Route path="order" element={<Order />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route element={<RequireAdmin />}>
            <Route path="admin" element={<Admin />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
