import { Link } from 'react-router-dom';
import '@/styles/static.css';

const CARDS = [
  { img: 'photo-1579829366248-204fe8413f31', icon: '🚁', title: 'Drone Delivery', text: 'Autonomous drone dispatch for fast, contactless delivery of packages up to 25 kg.' },
  { img: 'photo-1600891963933-9609d3a9b9b2', icon: '🍱', title: 'Food Delivery', text: 'Hot, fresh meals from your favourite restaurants delivered in record time.' },
  { img: 'photo-1563013544-824ae1b704d3', icon: '📦', title: 'Parcel Delivery', text: 'Documents, gifts, or electronics — your package reaches its destination safely on schedule.' },
  { img: 'photo-1600267165517-98c47f4cda3a', icon: '⚡', title: 'Express Delivery', text: 'Need it fast? Same-day service within your city — quick, secure, and dependable.' },
  { img: 'photo-1621263764928-45a9920e3b23', icon: '🏢', title: 'Business Logistics', text: 'Scheduled corporate deliveries, bulk shipments, and logistics management for your growth.' },
  { img: 'photo-1586528116311-ad8dd3c8310d', icon: '🏭', title: 'Smart Warehousing', text: 'Cost-effective storage with automated inventory tools and seamless dispatch integration.' },
];

const PRICING = [
  ['Food Delivery', '30–60 min', '5 kg', '$3.99 / order'],
  ['Parcel Delivery', 'Same day', '15 kg', '$5.99 / package'],
  ['Express Delivery', 'Within 2 hours', '10 kg', '$9.99 / package'],
  ['Drone Delivery', '1–3 hours', '25 kg', '$5.00 + $2.50/kg'],
  ['Business Logistics', 'Custom schedule', 'Unlimited', 'Contact Us'],
] as const;

export default function Services() {
  return (
    <>
      <div className="page-hero">
        <h1>Our Services</h1>
        <p>Fast. Reliable. Affordable — we deliver it all.</p>
      </div>
      <div className="services-layout">
        <div className="section-label">What We Offer</div>
        <h2 className="section-title">Delivery solutions for every need</h2>
        <div className="services-grid">
          {CARDS.map((c) => (
            <div className="service-card" key={c.title}>
              <img src={`https://images.unsplash.com/${c.img}?w=600`} alt={c.title} loading="lazy" />
              <div className="service-card-body">
                <span className="service-icon">{c.icon}</span>
                <h3>{c.title}</h3>
                <p>{c.text}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="pricing-section">
          <h2>💰 Pricing Plans</h2>
          <table className="pricing-table">
            <thead>
              <tr><th>Service</th><th>Delivery Time</th><th>Max Weight</th><th>Starting Price</th></tr>
            </thead>
            <tbody>
              {PRICING.map(([service, time, weight, price]) => (
                <tr key={service}>
                  <td>{service}</td><td>{time}</td><td>{weight}</td><td className="price-cell">{price}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="cta-banner">
          <div>
            <h3>Ready to fly your first package?</h3>
            <p>Sign up free and place your first order in under 2 minutes.</p>
          </div>
          <Link to="/order" className="btn btn-white btn-lg">🚁 Order Now</Link>
        </div>
      </div>
    </>
  );
}
