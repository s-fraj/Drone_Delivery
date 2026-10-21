import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import '@/styles/auth.css';
import { useAuth } from '@/auth/AuthContext';
import { ErrorBox } from '@/components/ui';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const user = await login(email, password);
      navigate(user.is_admin ? '/admin' : (from ?? '/profile'), { replace: true });
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : 'Login failed');
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-box">
        <div className="auth-logo">Drovery</div>
        <p className="auth-tagline">Drone-powered delivery at your fingertips</p>
        <h2 className="auth-title">Welcome back</h2>
        {error && <ErrorBox>{error}</ErrorBox>}
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input id="email" type="email" placeholder="you@example.com" required autoComplete="email"
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" placeholder="••••••••" required autoComplete="current-password"
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <div className="divider"><span /><p>Don't have an account?</p><span /></div>
        <div className="auth-footer"><Link to="/signup">Create a free account →</Link></div>
      </div>
    </div>
  );
}
