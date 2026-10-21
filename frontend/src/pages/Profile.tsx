import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '@/styles/profile.css';
import { useAuth } from '@/auth/AuthContext';
import { Modal } from '@/components/Modal';
import { useToast } from '@/components/Toast';
import { Empty, StatusBadge } from '@/components/ui';
import {
  useLocationMutations, useLocations, useOrderMutations, useOrders, useOrder, useTracking,
} from '@/hooks/queries';
import { useStatusAlerts } from '@/hooks/useStatusAlerts';
import { alertsPref, notificationsSupported } from '@/lib/alerts';
import { MISSION_LABELS, STATUS_PROGRESS, isTerminal, prettyStatus } from '@/lib/labels';
import { openReceipt } from '@/lib/receipt';
import type { Order } from '@/lib/types';

function Stars({ order, onRate }: { order: Order; onRate: (n: number) => void }) {
  const [hover, setHover] = useState(0);
  if (order.rating) {
    return <div className="stars done">{'★'.repeat(order.rating)}{'☆'.repeat(5 - order.rating)}</div>;
  }
  return (
    <div className="stars" onMouseLeave={() => setHover(0)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" className={`star${n <= hover ? ' on' : ''}`} aria-label={`Rate ${n} stars`}
          onMouseEnter={() => setHover(n)} onClick={() => onRate(n)}>
          ☆
        </button>
      ))}
    </div>
  );
}

function OrderCard({ order, active, onTrack }: { order: Order; active: boolean; onTrack: () => void }) {
  const { cancel, rate } = useOrderMutations();
  const stops = [order.dropoff_address, ...(order.extra_dropoffs ?? []).map((d) => d.address)];

  const onCancel = () => {
    if (!confirm('Cancel this order? If a drone is already flying it, it will return to base immediately.')) return;
    cancel.mutate(order.id, { onError: (e) => alert('Could not cancel: ' + e.message) });
  };

  return (
    <div className="order-card">
      <div className="order-top">
        <div>
          <div className="order-id">Order #{order.id}</div>
          <div className="order-route">
            📦 <b>{order.pickup_address}</b>
            {stops.length > 1
              ? stops.map((a, i) => <div key={i}><span className="addr">→ Stop {i + 1}: {a}</span></div>)
              : <div><span className="addr">→ {order.dropoff_address}</span></div>}
          </div>
        </div>
        <StatusBadge status={order.status} />
      </div>
      <div className="order-footer">
        <div>
          <div className="order-price">${order.price.toFixed(2)}</div>
          <div className="order-date">{new Date(order.created_at).toLocaleDateString()}</div>
          {order.status === 'delivered' && (
            <Stars order={order} onRate={(n) => rate.mutate({ id: order.id, rating: n }, {
              onError: (e) => alert('Could not submit rating: ' + e.message),
            })} />
          )}
        </div>
        {active ? (
          <div className="order-actions">
            <button className="btn btn-outline btn-sm" onClick={onTrack}>🚁 Track</button>
            <button className="btn btn-outline btn-sm btn-danger-outline" onClick={onCancel} disabled={cancel.isPending}>✕ Cancel</button>
          </div>
        ) : (
          <button className="btn btn-outline btn-sm" onClick={() => openReceipt(order)}>🧾 Receipt</button>
        )}
      </div>
    </div>
  );
}

function TrackModal({ orderId, onClose }: { orderId: number | null; onClose: () => void }) {
  const { data: order } = useOrder(orderId, true);
  const { data: t } = useTracking(orderId);
  const pct = order ? STATUS_PROGRESS[order.status] : 0;
  const route = order ? [order.pickup_address, order.dropoff_address, ...(order.extra_dropoffs ?? []).map((d) => d.address)].join(' → ') : '—';

  return (
    <Modal open={orderId !== null} onClose={onClose} title={<>🚁 Live Tracking — #{orderId}</>}>
      <div className="track-modal">
        <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%` }} /></div>
        <p style={{ fontSize: '0.78rem', color: 'var(--muted)', marginBottom: '1rem' }}>
          Status: {order ? `${prettyStatus(order.status).toUpperCase()} (${pct}%)` : '—'}
        </p>
        {t?.error_message && <div className="track-error">⚠️ {t.error_message}</div>}
        <div className="track-stat">
          <div className="track-item">
            <div className="tl">🚁 Mission Status</div>
            <div className="tv">{t ? (MISSION_LABELS[t.mission_status] ?? t.mission_status ?? 'Not dispatched') : '—'}</div>
          </div>
          <div className="track-item">
            <div className="tl">🤖 Assigned Drone</div>
            <div className="tv">{t?.drone_number ? `Drone #${t.drone_number}` : '—'}</div>
          </div>
        </div>
        {t?.queue_position ? (
          <div className="track-item"><div className="tl">⏳ Queue Position</div><div className="tv">#{t.queue_position} in line</div></div>
        ) : null}
        {t?.distance_km != null && (
          <div className="track-item"><div className="tl">📍 Distance away</div><div className="tv">📍 {t.distance_km} km away</div></div>
        )}
        {t?.stops_total != null && t.stops_total > 1 && (
          <div className="track-item"><div className="tl">📦 Stops</div><div className="tv">Stop {(t.stops_done ?? 0) + 1} of {t.stops_total}</div></div>
        )}
        <div className="track-item"><div className="tl">🛣️ Route</div><div className="tv" style={{ fontSize: '0.85rem' }}>{route}</div></div>
      </div>
    </Modal>
  );
}

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: orders } = useOrders();
  const { data: locations } = useLocations();
  const { add, remove } = useLocationMutations();
  useStatusAlerts(orders);

  const [trackId, setTrackId] = useState<number | null>(null);
  const [locOpen, setLocOpen] = useState(false);
  const [loc, setLoc] = useState({ label: '', address: '' });
  const [alertsOn, setAlertsOn] = useState(alertsPref.get());

  const { active, history, total } = useMemo(() => {
    const all = orders ?? [];
    return {
      active: all.filter((o) => !isTerminal(o.status)),
      history: all.filter((o) => isTerminal(o.status)),
      total: all.reduce((s, o) => s + o.price, 0),
    };
  }, [orders]);

  const enableAlerts = async () => {
    alertsPref.set(true);
    setAlertsOn(true);
    if (!notificationsSupported()) {
      return toast('Alerts enabled (sound + on-page only — this browser has no desktop notifications).');
    }
    const perm = await Notification.requestPermission();
    toast(perm === 'granted'
      ? "Delivery alerts enabled — you'll get a sound + notification while this site is open."
      : 'Sound alerts enabled. Allow notifications in your browser settings for desktop pop-ups too.');
  };

  const saveLocation = () => {
    const label = loc.label.trim();
    const address = loc.address.trim();
    if (!label || !address) return alert('Please fill both fields.');
    add.mutate({ label, address }, {
      onSuccess: () => { setLocOpen(false); setLoc({ label: '', address: '' }); },
    });
  };

  const icons: Record<string, string> = { Home: '🏠', Office: '🏢' };

  return (
    <div className="profile-page">
      <div className="profile-layout">
        <aside className="sidebar">
          <div className="user-card">
            <div className="avatar">{user?.first_name[0]?.toUpperCase() ?? '?'}</div>
            <div className="user-name">{user ? `${user.first_name} ${user.last_name}` : 'Loading…'}</div>
            <div className="user-email">{user?.email}</div>
            <div className="user-meta">
              <div><div className="num">{orders ? orders.length : '—'}</div><div className="lbl">Orders</div></div>
              <div><div className="num">{orders ? `$${total.toFixed(0)}` : '—'}</div><div className="lbl">Spent</div></div>
            </div>
          </div>
          <Link to="/order" className="btn btn-primary">🚁 New Order</Link>
          <button className="btn btn-ghost" onClick={() => { logout(); navigate('/login'); }}>Sign Out</button>
        </aside>

        <main className="main-content">
          <div className="card">
            <div className="section-hdr">
              <h2>🟢 Active Orders</h2>
              <div className="hdr-actions">
                {!alertsOn && <button className="btn btn-outline btn-sm" onClick={() => void enableAlerts()}>🔔 Enable delivery alerts</button>}
                <Link to="/order" className="btn btn-outline btn-sm">+ New</Link>
              </div>
            </div>
            {active.length
              ? active.map((o) => <OrderCard key={o.id} order={o} active onTrack={() => setTrackId(o.id)} />)
              : <Empty icon="📭">No active orders</Empty>}
          </div>

          <div className="card">
            <div className="section-hdr"><h2>📦 Order History</h2></div>
            {history.length
              ? history.map((o) => <OrderCard key={o.id} order={o} active={false} onTrack={() => undefined} />)
              : <Empty icon="📋">No past orders yet</Empty>}
          </div>

          <div className="card">
            <div className="section-hdr">
              <h2>📍 Saved Locations</h2>
              <button className="btn btn-outline btn-sm" onClick={() => setLocOpen(true)}>+ Add</button>
            </div>
            {locations?.length ? locations.map((l) => (
              <div className="loc-item" key={l.id}>
                <div>
                  <span className="loc-icon">{icons[l.label] ?? '📍'}</span>
                  <b>{l.label}</b> — <span style={{ color: 'var(--muted)', fontSize: '0.88rem' }}>{l.address}</span>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => remove.mutate(l.id)}>✕</button>
              </div>
            )) : <Empty>No saved locations yet</Empty>}
          </div>
        </main>
      </div>

      <TrackModal orderId={trackId} onClose={() => setTrackId(null)} />

      <Modal open={locOpen} title="Add Saved Location" onClose={() => setLocOpen(false)}>
        <div className="form-group">
          <label>Label (e.g. Home, Office)</label>
          <input type="text" placeholder="Home" value={loc.label} onChange={(e) => setLoc({ ...loc, label: e.target.value })} />
        </div>
        <div className="form-group">
          <label>Full Address</label>
          <input type="text" placeholder="45 King Street, Medenine" value={loc.address} onChange={(e) => setLoc({ ...loc, address: e.target.value })} />
        </div>
        <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={saveLocation} disabled={add.isPending}>
          Save Location
        </button>
      </Modal>
    </div>
  );
}
