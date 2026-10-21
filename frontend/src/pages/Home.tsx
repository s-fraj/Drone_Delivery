import { Link } from 'react-router-dom';
import '@/styles/home.css';
import { FallbackImg } from '@/components/FallbackImg';
import { useCountUp } from '@/hooks/useCountUp';

const FEATURES = [
  { icon: '⚡', title: 'Express', text: 'Shipments delivered anywhere in the country within 24 hours, guaranteed.' },
  { icon: '📡', title: 'Traceability', text: 'Track every package in real time — live status, distance away & stop progress.' },
  { icon: '💳', title: 'Payment', text: 'Secure card payments processed instantly at order placement.' },
  { icon: '🏭', title: 'Storage', text: 'Cost-effective warehouse solutions with efficient inventory management.' },
];

const STEPS = [
  { title: 'Create Account', text: 'Sign up in seconds. No paperwork, no waiting — just fill in your details.' },
  { title: 'Place Your Order', text: 'Pick your pickup & drop-off points on the map, add package details, and pay by card.' },
  { title: 'Drone Dispatched', text: 'The nearest free drone is automatically assigned and takes off.' },
  { title: 'Track Live', text: 'Follow your delivery in real time — status, distance away and stop progress.' },
];

const SERVICES = [
  { icon: '🚁', title: 'Drone Delivery', text: 'Autonomous drone dispatch for fast, contactless package delivery.' },
  { icon: '📡', title: 'Live Tracking', text: 'Real-time tracking of your delivery from takeoff to landing.' },
  { icon: '💳', title: 'Secure Payments', text: 'Encrypted card payments processed instantly at checkout.' },
  { icon: '🏭', title: 'Warehousing', text: 'Smart storage solutions with automated inventory management.' },
  { icon: '⚡', title: 'Express Routes', text: 'Priority lanes for same-hour deliveries within city limits.' },
  { icon: '🏢', title: 'B2B Logistics', text: 'Bulk delivery contracts and custom routes for businesses.' },
];

const STATS = [
  { label: 'Orders', target: 1200 },
  { label: 'Drones', target: 350 },
  { label: 'Employees', target: 85 },
  { label: 'Clients', target: 500 },
];

function Stat({ label, target }: { label: string; target: number }) {
  const { ref, value } = useCountUp<HTMLHeadingElement>(target);
  return (
    <div className="container-static">
      <h1 className="number" ref={ref}>+{value.toLocaleString()}</h1>
      <h2>{label}</h2>
    </div>
  );
}

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-content">
          <p style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--blue)', marginBottom: '0.8rem' }}>
            ● Next-gen delivery
          </p>
          <h1>Your Package,<br /><span>Airborne</span> in Minutes.</h1>
          <p>Drovery deploys autonomous drones for ultra-fast, real-time tracked deliveries straight to your door.</p>
          <div className="hero-btns">
            <Link to="/order" className="btn btn-primary btn-lg">🚁 Schedule Delivery</Link>
            <Link to="/about" className="btn btn-ghost btn-lg">Learn More</Link>
          </div>
        </div>
        <div className="hero-photo">
          <FallbackImg src="/drone-delivery.jpg" fallback="https://images.unsplash.com/photo-1579829366248-204fe8413f31?w=600" alt="Drone delivery" />
        </div>
      </section>

      <section className="features-section">
        <div className="features-inner">
          <div className="features-label">Why Drovery</div>
          <h2 className="features-title">Built for speed, trust &amp; scale</h2>
          <div className="feature-boxes">
            {FEATURES.map((f) => (
              <div className="feature-box" key={f.title}>
                <div className="feature-icon">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="info-section">
        <FallbackImg src="/DroneThumbnail.jpg" fallback="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600" alt="About Drovery" className="info-image" />
        <div className="info-text">
          <div className="features-label">Our Story</div>
          <h2>Delivery reimagined from the sky</h2>
          <p>At Drovery, our mission is to offer you an exceptional delivery experience. We are constantly dedicated to improving our services and ensuring your needs are addressed effectively and on time.</p>
          <p>Our team is committed to maintaining high standards of professionalism and integrity, while keeping customer satisfaction at the center of everything we do.</p>
          <Link to="/about" className="more-link">More about us →</Link>
        </div>
      </section>

      <div className="container-statics">
        <div className="stats-inner">
          {STATS.map((s) => <Stat key={s.label} {...s} />)}
        </div>
      </div>

      <section className="steps-section">
        <div className="steps-inner">
          <div className="steps-title"><h3>How it works</h3><h2>Drovery</h2></div>
          <div className="steps-grid">
            {STEPS.map((s, i) => (
              <div className="step" key={s.title}>
                <div className="step-number">{i + 1}</div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="service-container">
        <div className="services-inner">
          <div className="services-title">
            <div className="section-label">What we offer</div>
            <h2 className="section-title">Our Services</h2>
          </div>
          <div className="services">
            {SERVICES.map((s) => (
              <div className="service-box" key={s.title}>
                <div className="service-header">
                  <span style={{ fontSize: '1.5rem' }}>{s.icon}</span>
                  <h3 className="service-title">{s.title}</h3>
                </div>
                <hr className="service-line" />
                <p className="service-desc">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
