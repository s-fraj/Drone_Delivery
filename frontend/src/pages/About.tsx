import { Link } from 'react-router-dom';
import '@/styles/static.css';
import { FallbackImg } from '@/components/FallbackImg';

const VALUES = [
  { icon: '⚡', title: 'Speed', text: 'We relentlessly optimize for delivery time without compromising safety or quality.' },
  { icon: '🔒', title: 'Trust', text: 'Every package is handled with care. Transparent tracking builds confidence.' },
  { icon: '🌱', title: 'Sustainability', text: "Electric drones mean zero road emissions. We're delivering a greener future." },
];

export default function About() {
  return (
    <>
      <div className="page-hero">
        <h1>About Drovery</h1>
        <p>Delivering smiles — one flight at a time.</p>
      </div>

      <div className="about-content">
        <div className="about-text">
          <div className="section-label">Who We Are</div>
          <h2>We're rethinking the last mile</h2>
          <p>Drovery is a drone delivery company built to solve the "last mile" problem. We combine autonomous flight technology with a seamless user experience to make deliveries faster, greener, and more reliable than ever.</p>
          <p>With a growing fleet of drones and partners across multiple cities, we serve thousands of satisfied customers every day — bringing convenience and peace of mind straight to their doors.</p>
          <Link to="/order" className="btn btn-primary">🚁 Try it now</Link>
        </div>
        <div className="about-img">
          <FallbackImg src="/DroneThumbnail.jpg" fallback="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=700" alt="About Drovery" />
        </div>
      </div>

      <section className="mission-section">
        <div className="mission-inner">
          <div className="mission-text">
            <h3><span>Our Mission</span></h3>
            <p>To simplify delivery for everyone — individuals and businesses alike. We empower local vendors, support sustainable practices, and provide a logistics platform customers can always rely on.</p>
            <h3><span>Our Vision</span></h3>
            <p>To become the most trusted delivery partner across the country, recognized for innovation, integrity, and outstanding customer satisfaction.</p>
            <Link to="/services" className="btn btn-outline">Explore Services →</Link>
          </div>
          <div className="mission-img">
            <img src="https://images.unsplash.com/photo-1593642632559-0c6d3fc62b8f?w=600" alt="Mission" />
          </div>
        </div>
      </section>

      <section className="values-section">
        <div className="section-label">Our Values</div>
        <h2 className="section-title">What drives us</h2>
        <div className="values-grid">
          {VALUES.map((v) => (
            <div className="value-card" key={v.title}>
              <div className="value-icon">{v.icon}</div>
              <h4>{v.title}</h4>
              <p>{v.text}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
