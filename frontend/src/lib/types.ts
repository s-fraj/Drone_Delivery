// Types mirroring backend/schemas.py — keep in sync with the FastAPI models.

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'dispatched'
  | 'in_transit'
  | 'delivered'
  | 'cancelled';

export type PaymentStatus = 'unpaid' | 'paid' | 'failed';

export const ORDER_STATUSES: readonly OrderStatus[] = [
  'pending',
  'confirmed',
  'dispatched',
  'in_transit',
  'delivered',
  'cancelled',
] as const;

export interface User {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  is_admin: boolean;
  created_at: string;
}

export interface SignupInput {
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface ExtraDropoff {
  address: string;
  lat: number;
  lng: number;
}

export interface Order {
  id: number;
  pickup_address: string;
  dropoff_address: string;
  pickup_lat: number;
  pickup_lng: number;
  dropoff_lat: number;
  dropoff_lng: number;
  extra_dropoffs: ExtraDropoff[] | null;
  package_weight: number;
  package_desc: string | null;
  recipient_name: string | null;
  recipient_phone: string | null;
  notes: string | null;
  price: number;
  status: OrderStatus;
  payment_status: PaymentStatus;
  created_at: string;
  estimated_delivery: string | null;
  rating: number | null;
  rating_comment: string | null;
}

export interface OrderCreate {
  pickup_address: string;
  dropoff_address: string;
  pickup_lat: number;
  pickup_lng: number;
  dropoff_lat: number;
  dropoff_lng: number;
  extra_dropoffs: ExtraDropoff[];
  package_weight: number;
  package_desc: string | null;
  recipient_name: string | null;
  recipient_phone: string | null;
  notes: string | null;
}

export interface PaymentInput {
  card_number: string;
  card_expiry: string;
  card_cvc: string;
  card_holder: string;
}

export interface TrackingInfo {
  order_id: number;
  mission_id: string | null;
  drone_number: string | null;
  mission_status: string;
  queue_position: number | null;
  error_message: string | null;
  distance_km: number | null;
  stops_total: number | null;
  stops_done: number | null;
  updated_at: string | null;
}

export interface SavedLocation {
  id: number;
  label: string;
  address: string;
  lat: number | null;
  lng: number | null;
}

export interface AdminOrder extends Order {
  user_id: number;
  user_name: string;
  user_email: string;
  tracking: TrackingInfo | null;
}

export interface ServiceStatus {
  accepting_orders: boolean;
  message: string | null;
}

export interface AuditLogEntry {
  id: number;
  admin_id: number;
  admin_name: string | null;
  action: string;
  details: string | null;
  created_at: string;
}

// ── Drone fleet (Flask service, proxied via /admin/fleet) ────────────
export type DroneStatus = 'idle' | 'busy' | 'returning_home' | 'offline';

export interface DroneState {
  status: DroneStatus;
  lat: number | null;
  lng: number | null;
  alt?: number | null;
  battery_pct: number | null;
  battery_source?: 'sim' | 'telemetry';
  trail?: [number, number][];
}

export interface FleetStatus {
  drones: Record<string, DroneState>;
  queue_length?: number;
  service_state?: ServiceStatus;
}
