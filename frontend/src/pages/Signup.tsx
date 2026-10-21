import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '@/styles/auth.css';
import { useAuth } from '@/auth/AuthContext';
import { ErrorBox } from '@/components/ui';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', phone: '', password: '', confirm: '' });
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirm) return setError('Passwords do not match.');
    setBusy(true);
    try {
      await signup({
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        phone: form.phone || null,
        password: form.password,
      });
      setDone(true);
      timer.current = window.setTimeout(() => navigate('/login'), 1500);
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : 'Sign up failed');
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-box wide">
        <div className="auth-logo">Drovery</div>
        <p className="auth-tagline">Join thousands already flying with us</p>
        <h2 className="auth-title">Create your account</h2>
        {error && <ErrorBox>{error}</ErrorBox>}
        {done && <div className="success-msg">Account created! Redirecting to login…</div>}
        <form onSubmit={onSubmit}>
          <div className="form-row">
            <div className="form-group"><label>First Name</label><input type="text" placeholder="Fraj" required value={form.firstName} onChange={set('firstName')} /></div>
            <div className="form-group"><label>Last Name</label><input type="text" placeholder="Selmi" required value={form.lastName} onChange={set('lastName')} /></div>
          </div>
          <div className="form-group"><label>Email Address</label><input type="email" placeholder="you@example.com" required autoComplete="email" value={form.email} onChange={set('email')} /></div>
          <div className="form-group"><label>Phone (optional)</label><input type="tel" placeholder="+216 XX XXX XXX" value={form.phone} onChange={set('phone')} /></div>
          <div className="form-group"><label>Password</label><input type="password" placeholder="Min. 8 characters" required minLength={8} autoComplete="new-password" value={form.password} onChange={set('password')} /></div>
          <div className="form-group"><label>Confirm Password</label><input type="password" placeholder="••••••••" required autoComplete="new-password" value={form.confirm} onChange={set('confirm')} /></div>
          <button type="submit" className="btn btn-primary" disabled={busy || done}>
            {busy ? 'Creating account…' : 'Create Account'}
          </button>
        </form>
        <p className="terms">By signing up you agree to our <a href="#" style={{ color: 'var(--blue)' }}>Terms of Service</a></p>
        <div className="auth-footer">Already have an account? <Link to="/login">Sign in →</Link></div>
      </div>
    </div>
  );
}
