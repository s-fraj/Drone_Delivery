import { useState, type FormEvent } from 'react';
import '@/styles/static.css';

const INFO = [
  { ic: '📍', label: 'Address', value: 'Medenine, Tunisia' },
  { ic: '📞', label: 'Phone', value: '+216 XX XXX XXX' },
  { ic: '✉️', label: 'Email', value: 'support@drovery.tn' },
];

export default function Contact() {
  const [sent, setSent] = useState(false);

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSent(true);
    e.currentTarget.reset();
  };

  return (
    <>
      <div className="page-hero">
        <h1>Contact Us</h1>
        <p>We're here to help 24/7 — reach out anytime!</p>
      </div>

      <div className="contact-layout">
        <div className="contact-info">
          <h3>Get In Touch</h3>
          <p>Have questions, feedback, or partnership inquiries? Our support team is always ready to assist you.</p>
          {INFO.map((i) => (
            <div className="info-item" key={i.label}>
              <span className="ic">{i.ic}</span>
              <div className="il"><b>{i.label}</b><span>{i.value}</span></div>
            </div>
          ))}
          <div className="info-item">
            <span className="ic">🕒</span>
            <div className="il">
              <b>Working Hours</b>
              <span>Mon–Sat: 8:00 AM – 10:00 PM<br />Sunday: 9:00 AM – 6:00 PM</span>
            </div>
          </div>
        </div>

        <div className="contact-form">
          <div className="card">
            <h3>Send a Message</h3>
            {sent && <div className="success-banner">✅ Message sent! We'll be in touch shortly.</div>}
            <form onSubmit={onSubmit}>
              <div className="form-row">
                <div className="form-group"><label>First Name</label><input type="text" placeholder="Fraj" required /></div>
                <div className="form-group"><label>Last Name</label><input type="text" placeholder="Selmi" required /></div>
              </div>
              <div className="form-group"><label>Email</label><input type="email" placeholder="you@example.com" required /></div>
              <div className="form-group"><label>Subject</label><input type="text" placeholder="How can we help?" required /></div>
              <div className="form-group"><label>Message</label><textarea rows={5} placeholder="Your message…" required style={{ resize: 'vertical' }} /></div>
              <button type="submit" className="btn btn-primary btn-submit">Send Message</button>
            </form>
          </div>
        </div>
      </div>

      <div className="map-section">
        <iframe
          title="Drovery location"
          src="https://www.openstreetmap.org/export/embed.html?bbox=10.45%2C33.32%2C10.54%2C33.37&layer=mapnik"
          height={380}
          loading="lazy"
        />
      </div>
    </>
  );
}
