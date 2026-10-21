import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div style={{ padding: '9rem 1.5rem 6rem', textAlign: 'center' }}>
      <div style={{ fontSize: '3rem' }}>🛰️</div>
      <h1 style={{ fontWeight: 900, margin: '0.5rem 0' }}>Page not found</h1>
      <p className="text-muted" style={{ marginBottom: '1.5rem' }}>This route is off the flight map.</p>
      <Link to="/" className="btn btn-primary">Back to Home</Link>
    </div>
  );
}
