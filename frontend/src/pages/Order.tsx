import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import '@/styles/order.css';
import { MapPickerModal, type PickedLocation } from '@/components/MapPicker';
import { ErrorBox } from '@/components/ui';
import { useOrderMutations, useServiceStatus } from '@/hooks/queries';
import { fmtCoord, reverseGeocode, type LatLng } from '@/lib/geo';
import { BASE_FEE, estimatePrice } from '@/lib/pricing';

type PickTarget = { kind: 'pickup' } | { kind: 'dropoff' } | { kind: 'extra'; index: number };

const fmtMoney = (n: number) => `$${n.toFixed(2)}`;

function formatCard(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, 16).replace(/(.{4})/g, '$1 ').trim();
}
function formatExpiry(raw: string): string {
  const v = raw.replace(/\D/g, '');
  return v.length >= 2 ? `${v.slice(0, 2)}/${v.slice(2, 4)}` : v;
}
function cardIcon(num: string): string {
  const d = num.replace(/\D/g, '');
  return d.startsWith('4') ? '💙' : d.startsWith('5') ? '🟠' : d.startsWith('3') ? '🟢' : '💳';
}

function LocationField(props: {
  label: string;
  value: PickedLocation | null;
  onPick: () => void;
  extra?: React.ReactNode;
}) {
  const { label, value, onPick, extra } = props;
  return (
    <div className="form-group">
      <label>{extra ?? label}</label>
      <input
        type="text"
        className="readonly-input"
        readOnly
        required
        value={value?.address ?? ''}
        placeholder="Click to choose on map"
        onClick={onPick}
      />
      <div className="coord-display">{value ? fmtCoord(value) : 'No location selected yet'}</div>
    </div>
  );
}

export default function Order() {
  const status = useServiceStatus();
  const { place } = useOrderMutations();

  const [pickup, setPickup] = useState<PickedLocation | null>(null);
  const [dropoff, setDropoff] = useState<PickedLocation | null>(null);
  const [extras, setExtras] = useState<(PickedLocation | null)[]>([]);
  const [target, setTarget] = useState<PickTarget | null>(null);
  const [locating, setLocating] = useState(false);

  const [pkg, setPkg] = useState({ weight: '', desc: '', recipient: '', phone: '', notes: '' });
  const [card, setCard] = useState({ holder: '', number: '', expiry: '', cvc: '' });
  const [error, setError] = useState<string | null>(null);
  const [placed, setPlaced] = useState(false);

  const weight = parseFloat(pkg.weight) || 0;
  const setExtra = (i: number, v: PickedLocation | null) =>
    setExtras((xs) => xs.map((x, idx) => (idx === i ? v : x)));

  const price = useMemo(() => {
    const filled = extras.filter((e): e is PickedLocation => e !== null);
    const route: LatLng[] = pickup && dropoff ? [pickup, dropoff, ...filled] : [];
    return estimatePrice(weight, route, filled.length);
  }, [weight, pickup, dropoff, extras]);

  const pickerInitial: LatLng | null = !target
    ? null
    : target.kind === 'pickup' ? pickup
    : target.kind === 'dropoff' ? dropoff
    : (extras[target.index] ?? null);

  const pickerTitle = !target ? '' : target.kind === 'pickup' ? 'Choose pickup location'
    : target.kind === 'dropoff' ? 'Choose drop-off location'
    : `Choose drop-off #${target.index + 2} location`;

  const onPicked = (loc: PickedLocation) => {
    if (!target) return;
    if (target.kind === 'pickup') setPickup(loc);
    else if (target.kind === 'dropoff') setDropoff(loc);
    else setExtra(target.index, loc);
    setTarget(null);
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) return alert('Geolocation is not supported by this browser.');
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setPickup({ ...p, address: await reverseGeocode(p) });
        setLocating(false);
      },
      () => {
        setLocating(false);
        alert('Could not get your location. Please try the map instead.');
      },
    );
  };

  const submit = async () => {
    setError(null);
    if (!pickup || !dropoff || !weight) {
      return setError('Please fill in all required fields.');
    }
    const filled = extras.filter((e): e is PickedLocation => e !== null);
    if (filled.length !== extras.length) {
      return setError('Please pick a location on the map for every extra drop-off (or remove it).');
    }
    try {
      await place.mutateAsync({
        order: {
          pickup_address: pickup.address,
          dropoff_address: dropoff.address,
          pickup_lat: pickup.lat,
          pickup_lng: pickup.lng,
          dropoff_lat: dropoff.lat,
          dropoff_lng: dropoff.lng,
          extra_dropoffs: filled.map(({ address, lat, lng }) => ({ address, lat, lng })),
          package_weight: weight,
          package_desc: pkg.desc || null,
          recipient_name: pkg.recipient || null,
          recipient_phone: pkg.phone || null,
          notes: pkg.notes || null,
        },
        payment: {
          card_number: card.number.replace(/\s/g, ''),
          card_expiry: card.expiry,
          card_cvc: card.cvc,
          card_holder: card.holder,
        },
      });
      setPlaced(true);
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : 'Could not place the order');
    }
  };

  const paused = status.data && !status.data.accepting_orders;

  return (
    <div className="order-page">
      <div className="order-layout">
        <h1>🚁 Schedule a Delivery</h1>
        <p className="subtitle">Fill in the details below — your drone will be dispatched immediately after payment.</p>

        {paused ? (
          <div className="paused">
            <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>🛠️</div>
            <h2>Ordering is temporarily paused</h2>
            <p className="text-muted">
              {status.data?.message ?? "We're not accepting new orders right now — please check back shortly."}
            </p>
            <Link to="/" className="btn btn-outline">Back to Home</Link>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            {error && <ErrorBox>{error}</ErrorBox>}

            <div className="card">
              <div className="step-header"><div className="step-num">1</div><h3>Pickup &amp; Drop-off</h3></div>
              <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '-0.4rem 0 1rem' }}>
                📍 GPS coordinates are required for every point — the drone flies to exact coordinates, not to street addresses.
              </p>
              <LocationField label="Pickup Address" value={pickup} onPick={() => setTarget({ kind: 'pickup' })} />
              <button type="button" className="btn btn-ghost btn-sm" onClick={useMyLocation} disabled={locating}>
                {locating ? 'Locating…' : '📍 Use my current location for pickup'}
              </button>
              <div style={{ marginTop: '1rem' }}>
                <LocationField label="Drop-off Address" value={dropoff} onPick={() => setTarget({ kind: 'dropoff' })} />
              </div>

              {extras.map((stop, i) => (
                <div className="extra-stop" key={i}>
                  <LocationField
                    label={`Drop-off #${i + 2}`}
                    value={stop}
                    onPick={() => setTarget({ kind: 'extra', index: i })}
                    extra={
                      <span className="extra-stop-hdr">
                        <span>Drop-off #{i + 2}</span>
                        <button type="button" className="link-danger" onClick={() => setExtras((xs) => xs.filter((_, idx) => idx !== i))}>
                          ✕ Remove
                        </button>
                      </span>
                    }
                  />
                </div>
              ))}
              <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: '0.8rem' }} onClick={() => setExtras((xs) => [...xs, null])}>
                + Add another drop-off
              </button>
            </div>

            <div className="card">
              <div className="step-header"><div className="step-num">2</div><h3>Package Details</h3></div>
              <div className="form-row">
                <div className="form-group">
                  <label>Weight (kg) *</label>
                  <input type="number" min="0.1" max="25" step="0.1" placeholder="e.g. 2.5" required
                    value={pkg.weight} onChange={(e) => setPkg({ ...pkg, weight: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Package Description</label>
                  <input type="text" placeholder="e.g. Documents, electronics…" value={pkg.desc} onChange={(e) => setPkg({ ...pkg, desc: e.target.value })} />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Recipient Name</label>
                  <input type="text" placeholder="Full name" value={pkg.recipient} onChange={(e) => setPkg({ ...pkg, recipient: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Recipient Phone</label>
                  <input type="tel" placeholder="+216 XX XXX XXX" value={pkg.phone} onChange={(e) => setPkg({ ...pkg, phone: e.target.value })} />
                </div>
              </div>
              <div className="form-group">
                <label>Special Notes</label>
                <input type="text" placeholder="Handle with care, leave at door, etc." value={pkg.notes} onChange={(e) => setPkg({ ...pkg, notes: e.target.value })} />
              </div>
            </div>

            <div className="price-preview">
              <div className="label">Estimated Total</div>
              <div className="amount">{fmtMoney(price.total)}</div>
              <div className="price-breakdown">
                <span>Base fee: <b>{fmtMoney(BASE_FEE)}</b></span>
                <span>Weight: <b>{fmtMoney(price.weight)}</b></span>
                <span>Distance: <b>{fmtMoney(price.distance)}</b></span>
                {price.extraStops > 0 && <span>Extra stops: <b>{fmtMoney(price.extraStops)}</b></span>}
              </div>
            </div>

            <div className="card">
              <div className="step-header"><div className="step-num">3</div><h3>Card Payment</h3></div>
              <div className="form-group">
                <label>Cardholder Name</label>
                <input type="text" placeholder="Name on card" required autoComplete="cc-name" value={card.holder} onChange={(e) => setCard({ ...card, holder: e.target.value })} />
              </div>
              <div className="form-group card-field">
                <label>Card Number</label>
                <input type="text" inputMode="numeric" maxLength={19} placeholder="1234 5678 9012 3456" required autoComplete="cc-number"
                  value={card.number} onChange={(e) => setCard({ ...card, number: formatCard(e.target.value) })} />
                <span className="card-icon">{cardIcon(card.number)}</span>
              </div>
              <div className="card-row">
                <div className="form-group">
                  <label>Expiry Date</label>
                  <input type="text" inputMode="numeric" maxLength={5} placeholder="MM/YY" required autoComplete="cc-exp"
                    value={card.expiry} onChange={(e) => setCard({ ...card, expiry: formatExpiry(e.target.value) })} />
                </div>
                <div className="form-group">
                  <label>CVC</label>
                  <input type="text" inputMode="numeric" maxLength={4} placeholder="•••" required autoComplete="cc-csc"
                    value={card.cvc} onChange={(e) => setCard({ ...card, cvc: e.target.value.replace(/\D/g, '') })} />
                </div>
                <div />
              </div>
            </div>

            <div className="submit-area">
              <p className="text-muted" style={{ fontSize: '0.82rem' }}>🔒 Secured with 256-bit TLS encryption</p>
              <button type="submit" className="btn btn-primary submit-btn" disabled={place.isPending}>
                {place.isPending ? 'Placing order…' : 'Place Order & Pay'}
              </button>
            </div>
          </form>
        )}
      </div>

      <MapPickerModal
        open={target !== null}
        title={pickerTitle}
        initial={pickerInitial}
        onClose={() => setTarget(null)}
        onConfirm={onPicked}
      />

      {placed && (
        <div className="success-overlay">
          <div className="success-box">
            <div className="success-icon">🚁</div>
            <h2>Order Placed!</h2>
            <p>Your drone is being dispatched. You can track it live from your profile.</p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <Link to="/profile" className="btn btn-primary">Track My Order</Link>
              <Link to="/" className="btn btn-ghost">Back to Home</Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
