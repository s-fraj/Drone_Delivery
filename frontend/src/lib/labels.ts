import type { OrderStatus } from './types';

export const STATUS_PROGRESS: Record<OrderStatus, number> = {
  pending: 5,
  confirmed: 20,
  dispatched: 40,
  in_transit: 70,
  delivered: 100,
  cancelled: 0,
};

// Customer-facing copy for each internal mission phase — never raw status text.
export const MISSION_LABELS: Record<string, string> = {
  'Not dispatched': 'Preparing your delivery',
  'Waiting for drone': 'Preparing your delivery',
  'Taking off': 'Drone departing',
  'Going to pickup': 'En route to pickup',
  'Package picked': 'Package secured',
  'Going to client': 'On the way to you',
  Delivered: 'Delivered',
  Completed: 'Delivered',
  'Dispatch failed': 'Preparing your delivery',
  Error: "We're resolving an issue with your delivery",
};

export const isTerminal = (s: OrderStatus): boolean => s === 'delivered' || s === 'cancelled';
export const prettyStatus = (s: string): string => s.replace(/_/g, ' ');
