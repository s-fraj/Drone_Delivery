import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { OSM_ATTRIBUTION, OSM_TILES } from './MapPicker';
import type { AdminOrder, DroneState, DroneStatus } from '@/lib/types';

const DRONE_COLORS: Record<DroneStatus, string> = {
  idle: '#16a34a',
  busy: '#d97706',
  returning_home: '#4f46e5',
  offline: '#9ca3af',
};

const emojiIcon = (html: string) =>
  L.divIcon({ html, className: 'order-pin', iconSize: [22, 22], iconAnchor: [11, 11] });
const PICKUP_ICON = emojiIcon('📦');
const DROPOFF_ICON = emojiIcon('🏁');

interface Props {
  drones: [string, DroneState][];
  orders: AdminOrder[];
}

export function FleetMap({ drones, orders }: Props) {
  const inFlight = orders.filter((o) => o.status === 'dispatched' || o.status === 'in_transit');

  return (
    <MapContainer center={[33.343, 10.491]} zoom={13} className="fleet-map">
      <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} maxZoom={19} />

      {inFlight.map((o) => {
        const stops = [
          { lat: o.dropoff_lat, lng: o.dropoff_lng },
          ...(o.extra_dropoffs ?? []),
        ];
        const planned: [number, number][] = [
          [o.pickup_lat, o.pickup_lng],
          ...stops.map((s): [number, number] => [s.lat, s.lng]),
        ];
        return (
          <span key={o.id}>
            <Marker position={planned[0]!} icon={PICKUP_ICON}>
              <Tooltip>Order #{o.id} — pickup</Tooltip>
            </Marker>
            {stops.map((s, i) => (
              <Marker key={i} position={[s.lat, s.lng]} icon={DROPOFF_ICON}>
                <Tooltip>Order #{o.id} — drop-off{stops.length > 1 ? ` #${i + 1}` : ''}</Tooltip>
              </Marker>
            ))}
            {/* planned route, dashed to distinguish it from the flown trail */}
            <Polyline positions={planned} pathOptions={{ color: '#64748b', weight: 2, dashArray: '6 8', opacity: 0.6 }} />
          </span>
        );
      })}

      {drones.map(([id, d]) => {
        if (d.lat == null || d.lng == null) return null;
        const color = DRONE_COLORS[d.status] ?? '#64748b';
        const trail = d.trail ?? [];
        return (
          <span key={id}>
            {trail.length > 1 && <Polyline positions={trail} pathOptions={{ color, weight: 3, opacity: 0.8 }} />}
            <CircleMarker center={[d.lat, d.lng]} radius={9} pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 2 }}>
              <Tooltip>
                Drone #{id} — {d.status}
                {d.battery_pct != null ? ` — 🔋${Math.round(d.battery_pct)}%` : ''}
              </Tooltip>
            </CircleMarker>
          </span>
        );
      })}
    </MapContainer>
  );
}
