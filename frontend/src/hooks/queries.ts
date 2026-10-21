import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  AdminOrder,
  AuditLogEntry,
  FleetStatus,
  Order,
  OrderCreate,
  OrderStatus,
  PaymentInput,
  SavedLocation,
  ServiceStatus,
  TrackingInfo,
  User,
} from '@/lib/types';

// ── Customer ──────────────────────────────────────────────────────────
export const useServiceStatus = () =>
  useQuery({
    queryKey: ['public-service-status'],
    queryFn: () => api.get<ServiceStatus>('/public/service-status'),
    retry: false, // fail open on the UI; the backend enforces it on order creation
  });

/** Polled so Active → History moves without a manual refresh. */
export const useOrders = () =>
  useQuery({
    queryKey: ['orders'],
    queryFn: () => api.get<Order[]>('/orders'),
    refetchInterval: 8000,
  });

export const useOrder = (id: number | null, poll = false) =>
  useQuery({
    queryKey: ['order', id],
    queryFn: () => api.get<Order>(`/orders/${id}`),
    enabled: id !== null,
    refetchInterval: poll ? 5000 : false,
  });

export const useTracking = (id: number | null) =>
  useQuery({
    queryKey: ['tracking', id],
    queryFn: () => api.get<TrackingInfo>(`/orders/${id}/track`),
    enabled: id !== null,
    refetchInterval: 5000,
  });

export const useLocations = () =>
  useQuery({ queryKey: ['locations'], queryFn: () => api.get<SavedLocation[]>('/locations') });

export function useLocationMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['locations'] });
  return {
    add: useMutation({
      mutationFn: (v: { label: string; address: string }) => api.post<SavedLocation>('/locations', v),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api.delete(`/locations/${id}`),
      onSuccess: invalidate,
    }),
  };
}

export function useOrderMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ['orders'] });
  return {
    cancel: useMutation({
      mutationFn: (id: number) => api.post<Order>(`/orders/${id}/cancel`),
      onSuccess: refresh,
    }),
    rate: useMutation({
      mutationFn: (v: { id: number; rating: number }) =>
        api.post<Order>(`/orders/${v.id}/rating`, { rating: v.rating }),
      onSuccess: refresh,
    }),
    /** Create the order, then charge the card — same two-step flow as before. */
    place: useMutation({
      mutationFn: async (v: { order: OrderCreate; payment: PaymentInput }) => {
        const order = await api.post<Order>('/orders', v.order);
        await api.post(`/orders/${order.id}/pay`, v.payment);
        return order;
      },
      onSuccess: refresh,
    }),
  };
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: Partial<Pick<User, 'first_name' | 'last_name' | 'phone'>>) =>
      api.put<User>('/users/me', v),
    onSuccess: (u) => qc.setQueryData(['me'], u),
  });
}

// ── Admin ─────────────────────────────────────────────────────────────
export const useAdminFleet = () =>
  useQuery({
    queryKey: ['admin', 'fleet'],
    queryFn: () => api.get<FleetStatus>('/admin/fleet'),
    refetchInterval: 2000, // fast poll so movement reads as live
    retry: false,
  });

export const useDroneHealth = () =>
  useQuery({
    queryKey: ['admin', 'health'],
    queryFn: () => api.get<{ healthy: boolean }>('/admin/drone-service-health'),
    refetchInterval: 2000,
    retry: false,
  });

export const useAdminOrders = () =>
  useQuery({
    queryKey: ['admin', 'orders'],
    queryFn: () => api.get<AdminOrder[]>('/admin/orders'),
    refetchInterval: 8000,
  });

export const useAdminUsers = () =>
  useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api.get<User[]>('/admin/users'),
    refetchInterval: 8000,
  });

export const useAdminServiceState = () =>
  useQuery({
    queryKey: ['admin', 'service-state'],
    queryFn: () => api.get<ServiceStatus>('/admin/service-state'),
    refetchInterval: 8000,
  });

export const useAuditLog = () =>
  useQuery({ queryKey: ['admin', 'audit'], queryFn: () => api.get<AuditLogEntry[]>('/admin/audit-log') });

export function useAdminMutations() {
  const qc = useQueryClient();
  const refreshOrders = () => {
    qc.invalidateQueries({ queryKey: ['admin', 'orders'] });
    qc.invalidateQueries({ queryKey: ['admin', 'audit'] });
  };
  return {
    setStatus: useMutation({
      mutationFn: (v: { id: number; status: OrderStatus }) =>
        api.put<AdminOrder>(`/admin/orders/${v.id}/status`, { status: v.status }),
      onSettled: refreshOrders, // also resets the <select> if the change was rejected
    }),
    abort: useMutation({
      mutationFn: (id: number) => api.post<AdminOrder>(`/admin/orders/${id}/abort`),
      onSuccess: refreshOrders,
    }),
    retryDispatch: useMutation({
      mutationFn: (id: number) => api.post<AdminOrder>(`/admin/orders/${id}/retry-dispatch`),
      onSuccess: () => {
        refreshOrders();
        qc.invalidateQueries({ queryKey: ['admin', 'fleet'] });
      },
    }),
    setServiceState: useMutation({
      mutationFn: (v: ServiceStatus) => api.post<ServiceStatus>('/admin/service-state', v),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['admin', 'service-state'] });
        qc.invalidateQueries({ queryKey: ['admin', 'audit'] });
      },
    }),
    emergencyStop: useMutation({
      mutationFn: (message: string | null) =>
        api.post<ServiceStatus>('/admin/emergency-stop', { message }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['admin'] });
      },
    }),
  };
}
