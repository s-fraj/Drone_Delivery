import { routeKm, type LatLng } from './geo';

// Must mirror backend/crud.py calculate_price().
export const BASE_FEE = 5;
export const PER_KG = 2.5;
export const PER_KM = 0.5;
export const EXTRA_STOP_FEE = 3;

export interface PriceBreakdown {
  total: number;
  weight: number;
  distance: number;
  extraStops: number;
}

export function estimatePrice(
  weightKg: number,
  route: LatLng[], // pickup, dropoff, ...extras (only the points that are set)
  extraStopCount: number,
): PriceBreakdown {
  const weight = weightKg * PER_KG;
  const distance = route.length >= 2 ? routeKm(route) * PER_KM : 0;
  const extraStops = extraStopCount * EXTRA_STOP_FEE;
  return { total: BASE_FEE + weight + distance + extraStops, weight, distance, extraStops };
}
