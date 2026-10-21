import { useEffect, useState } from 'react';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import { Modal } from './Modal';
import { DEFAULT_CENTER, fmtCoord, reverseGeocode, searchAddress, type LatLng } from '@/lib/geo';

// Vite doesn't resolve Leaflet's default icon URLs, so wire them up explicitly.
export const pinIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

export const OSM_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
export const OSM_ATTRIBUTION = '© OpenStreetMap contributors';

function ClickToPin({ onPick }: { onPick: (p: LatLng) => void }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function Recenter({ to }: { to: LatLng }) {
  const map = useMap();
  useEffect(() => {
    map.setView([to.lat, to.lng], map.getZoom() < 15 ? 15 : map.getZoom());
  }, [to, map]);
  return null;
}

export interface PickedLocation extends LatLng {
  address: string;
}

interface Props {
  open: boolean;
  title: string;
  initial: LatLng | null;
  onClose: () => void;
  onConfirm: (loc: PickedLocation) => void;
}

export function MapPickerModal({ open, title, initial, onClose, onConfirm }: Props) {
  const [pin, setPin] = useState<LatLng | null>(initial);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [flyTo, setFlyTo] = useState<LatLng | null>(null);

  useEffect(() => {
    if (open) {
      setPin(initial);
      setQuery('');
      setFlyTo(null);
    }
  }, [open, initial]);

  const search = async () => {
    const q = query.trim();
    if (!q) return;
    try {
      const found = await searchAddress(q);
      if (!found) return alert('Address not found.');
      setPin(found);
      setFlyTo(found);
    } catch {
      alert('Search failed — check your connection.');
    }
  };

  const confirm = async () => {
    if (!pin) return;
    setBusy(true);
    const address = await reverseGeocode(pin);
    setBusy(false);
    onConfirm({ ...pin, address });
  };

  const center = initial ?? DEFAULT_CENTER;

  return (
    <Modal open={open} title={title} onClose={onClose} maxWidth={600}>
      <div className="map-search">
        <input
          type="text"
          value={query}
          placeholder="Search an address…"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), void search())}
        />
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void search()}>
          Search
        </button>
      </div>
      <MapContainer center={[center.lat, center.lng]} zoom={13} className="pick-map">
        <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} maxZoom={19} />
        <ClickToPin onPick={setPin} />
        {flyTo && <Recenter to={flyTo} />}
        {pin && <Marker position={[pin.lat, pin.lng]} icon={pinIcon} />}
      </MapContainer>
      <div className="coord-display">{pin ? `📍 ${fmtCoord(pin)}` : 'Click anywhere on the map to drop a pin'}</div>
      <button
        className="btn btn-primary"
        style={{ width: '100%', justifyContent: 'center', marginTop: '0.8rem' }}
        onClick={() => void confirm()}
        disabled={!pin || busy}
      >
        {busy ? 'Resolving address…' : 'Confirm this location'}
      </button>
    </Modal>
  );
}
