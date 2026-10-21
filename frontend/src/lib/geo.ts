export interface LatLng {
  lat: number;
  lng: number;
}

export const DEFAULT_CENTER: LatLng = { lat: 36.8065, lng: 10.1815 }; // Tunis

export function haversineKm(a: LatLng, b: LatLng): number {
  const R = 6371;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.sqrt(h));
}

export function routeKm(points: LatLng[]): number {
  let total = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (a && b) total += haversineKm(a, b);
  }
  return total;
}

export const fmtCoord = (p: LatLng): string => `${p.lat.toFixed(6)}, ${p.lng.toFixed(6)}`;

// ── Nominatim (OpenStreetMap) geocoding — no API key ───────────────────
export async function reverseGeocode(p: LatLng): Promise<string> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${p.lat}&lon=${p.lng}`,
    );
    const data = (await res.json()) as { display_name?: string };
    return data.display_name ?? fmtCoord(p);
  } catch {
    return fmtCoord(p);
  }
}

export async function searchAddress(query: string): Promise<LatLng | null> {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`,
  );
  const results = (await res.json()) as { lat: string; lon: string }[];
  const first = results[0];
  return first ? { lat: parseFloat(first.lat), lng: parseFloat(first.lon) } : null;
}
