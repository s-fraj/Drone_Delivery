import { useEffect, useMemo, useRef } from 'react';
import '@/styles/admin.css';
import { FleetMap } from '@/components/FleetMap';
import {
  useAdminFleet, useAdminMutations, useAdminOrders, useAdminServiceState, useAdminUsers,
  useAuditLog, useDroneHealth,
} from '@/hooks/queries';
import { api } from '@/lib/api';
import { desktopNotify, notificationsSupported, playTone } from '@/lib/alerts';
import { isTerminal, prettyStatus } from '@/lib/labels';
import { ORDER_STATUSES, type AdminOrder, type OrderStatus } from '@/lib/types';

const FINISHED_MISSION = ['Completed', 'Delivered', 'Error', 'Dispatch failed'];

/** Beep + desktop notification the first time an order shows a new dispatch error. */
function useErrorAlerts(orders: AdminOrder[] | undefined) {
  const previous = useRef<Map<number, string | null>>(new Map());
  useEffect(() => {
    if (!orders) return;
    for (const o of orders) {
      const err = o.tracking?.error_message ?? null;
      if (err && previous.current.get(o.id) !== err) {
        playTone('square', 660, 0.4, 0.1);
        desktopNotify('Drovery admin', `Order #${o.id}: ${err}`);
      }
      previous.current.set(o.id, err);
    }
  }, [orders]);
}

function isInFlight(o: AdminOrder): boolean {
  const t = o.tracking;
  return !!t?.mission_id && !FINISHED_MISSION.includes(t.mission_status) && !isTerminal(o.status);
}

function FleetCard() {
  const fleet = useAdminFleet();
  const health = useDroneHealth();
  const orders = useAdminOrders();
  const service = useAdminServiceState();
  const { setServiceState, emergencyStop } = useAdminMutations();

  const drones = useMemo(() => Object.entries(fleet.data?.drones ?? {}), [fleet.data]);
  const accepting = service.data?.accepting_orders ?? true;

  const togglePause = () => {
    if (accepting) {
      const message = prompt(
        'Message to show customers while paused (optional):',
        "We're briefly offline for maintenance — please check back shortly.",
      );
      if (message === null) return;
      setServiceState.mutate({ accepting_orders: false, message }, { onError: (e) => alert('Could not update service state: ' + e.message) });
    } else {
      setServiceState.mutate({ accepting_orders: true, message: null }, { onError: (e) => alert('Could not update service state: ' + e.message) });
    }
  };

  const triggerStop = () => {
    if (!confirm('Emergency stop: pauses new orders AND immediately recalls every airborne drone home. Continue?')) return;
    const message = prompt('Message to show customers (optional):', "We've paused deliveries for an emergency stop. All drones are returning to base.");
    emergencyStop.mutate(message, {
      onSuccess: (r) => alert(r.message ?? 'Emergency stop triggered.'),
      onError: (e) => alert('Could not trigger emergency stop: ' + e.message),
    });
  };

  const healthy = health.data?.healthy;

  return (
    <div className="card">
      <div className="section-hdr">
        <h2>🚁 Fleet Status</h2>
        <div>
          <span className="health">
            <span className={`health-dot ${health.isError || healthy === false ? 'down' : healthy ? 'up' : ''}`} />
            {health.isError || healthy === false ? 'Drone service unreachable' : healthy ? 'Drone service online' : 'Checking…'}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={() => { void fleet.refetch(); void orders.refetch(); }}>↻ Refresh</button>
        </div>
      </div>

      {fleet.isError ? (
        <div className="empty">Could not load fleet status — {fleet.error.message}</div>
      ) : !drones.length ? (
        <div className="empty">{fleet.isLoading ? 'Loading fleet…' : 'No drones configured on the fleet service.'}</div>
      ) : (
        <div className="fleet-grid">
          {drones.map(([id, d]) => (
            <div className={`drone-card ${d.status}`} key={id}>
              <div className="dnum">Drone #{id}</div>
              <div className="dstatus">{prettyStatus(d.status)}</div>
              {d.battery_pct != null && <div className="dbatt">🔋 {Math.round(d.battery_pct)}%</div>}
            </div>
          ))}
        </div>
      )}
      <div className="queue-pill">
        {fleet.data?.queue_length ? `⏳ ${fleet.data.queue_length} mission(s) waiting in queue` : ''}
      </div>

      <FleetMap drones={drones} orders={orders.data ?? []} />

      {!accepting && (
        <div className="service-banner">⏸ Paused — {service.data?.message ?? 'not accepting new orders.'}</div>
      )}
      <div className="service-controls">
        <button className="btn btn-outline btn-sm" onClick={togglePause} disabled={setServiceState.isPending}>
          {accepting ? '⏸ Pause new orders' : '▶ Resume orders'}
        </button>
        <button className="btn btn-outline btn-sm btn-danger-outline" onClick={triggerStop} disabled={emergencyStop.isPending}>
          🛑 Emergency Stop
        </button>
      </div>
    </div>
  );
}

function AuditCard() {
  const audit = useAuditLog();
  return (
    <div className="card">
      <div className="section-hdr">
        <h2>🧾 Admin Audit Log</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => void audit.refetch()}>↻ Refresh</button>
      </div>
      {audit.isError ? <div className="empty">Could not load audit log</div>
        : !audit.data ? <div className="empty">Loading…</div>
        : !audit.data.length ? <div className="empty">No admin actions yet</div>
        : audit.data.map((e) => (
          <div className="audit-entry" key={e.id}>
            <b>{e.admin_name ?? `Admin #${e.admin_id}`}</b> — {e.action.replace(/_/g, ' ')}
            {e.details && <span className="text-muted"> — {e.details}</span>}
            <div className="text-muted audit-time">{new Date(e.created_at).toLocaleString()}</div>
          </div>
        ))}
    </div>
  );
}

function OrderRow({ o }: { o: AdminOrder }) {
  const { setStatus, abort, retryDispatch } = useAdminMutations();
  const t = o.tracking;
  const canRetry = o.payment_status === 'paid' && (!t?.mission_id || !!t.error_message);
  const flying = isInFlight(o);
  const fail = (what: string) => (e: Error) => alert(`${what}: ${e.message}`);

  return (
    <tr>
      <td className="mono">#{o.id}</td>
      <td>{o.user_name}<br /><span className="text-muted sub">{o.user_email}</span></td>
      <td style={{ maxWidth: 220 }}>
        {o.pickup_address} → {o.dropoff_address}
        {o.extra_dropoffs?.length ? <span className="text-muted sub"> (+{o.extra_dropoffs.length} stops)</span> : null}
      </td>
      <td className="mono">${o.price.toFixed(2)}</td>
      <td><span className={`badge badge-${o.payment_status === 'paid' ? 'delivered' : 'pending'}`}>{o.payment_status}</span></td>
      <td>
        {flying ? (
          <span className="badge badge-pending" title="Status is driven by live drone telemetry while in flight — it isn't manually editable until delivered.">
            {prettyStatus(o.status)} 🚁
          </span>
        ) : (
          <select className="status-select" value={o.status}
            onChange={(e) => setStatus.mutate({ id: o.id, status: e.target.value as OrderStatus }, { onError: fail('Could not update status') })}>
            {ORDER_STATUSES.map((s) => <option key={s} value={s}>{prettyStatus(s)}</option>)}
          </select>
        )}
      </td>
      <td>
        {t?.mission_status ?? 'Not dispatched'}
        {t?.queue_position ? <><br /><span className="text-muted sub">#{t.queue_position} in queue</span></> : null}
        {t?.error_message && <div className="err-cell">⚠️ {t.error_message}</div>}
      </td>
      <td>
        <div className="row-actions">
          {canRetry && (
            <button className="btn btn-outline btn-sm" disabled={retryDispatch.isPending}
              onClick={() => retryDispatch.mutate(o.id, { onError: fail('Retry failed') })}>
              Retry Dispatch
            </button>
          )}
          {flying && (
            <button className="btn btn-outline btn-sm btn-danger-outline" disabled={abort.isPending}
              onClick={() => confirm('Abort this delivery? The drone will return to base immediately.') && abort.mutate(o.id, { onError: fail('Could not abort') })}>
              Abort
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function OrdersCard() {
  const orders = useAdminOrders();
  useErrorAlerts(orders.data);

  const exportCsv = () =>
    api.download('/admin/orders/export', 'orders.csv').catch((e: Error) => alert('Could not export orders: ' + e.message));

  return (
    <div className="card">
      <div className="section-hdr">
        <h2>📦 All Orders</h2>
        <button className="btn btn-outline btn-sm" onClick={() => void exportCsv()}>⬇ Export CSV</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>ID</th><th>Customer</th><th>Route</th><th>Price</th><th>Payment</th><th>Status</th><th>Mission</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {orders.isError ? <tr><td colSpan={8} className="empty">Could not load orders — {orders.error.message}</td></tr>
              : !orders.data ? <tr><td colSpan={8} className="empty">Loading orders…</td></tr>
              : !orders.data.length ? <tr><td colSpan={8} className="empty">No orders yet</td></tr>
              : orders.data.map((o) => <OrderRow key={o.id} o={o} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UsersCard() {
  const users = useAdminUsers();
  return (
    <div className="card">
      <div className="section-hdr"><h2>👥 Users</h2></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Joined</th></tr></thead>
          <tbody>
            {users.isError ? <tr><td colSpan={6} className="empty">Could not load users — {users.error.message}</td></tr>
              : !users.data ? <tr><td colSpan={6} className="empty">Loading users…</td></tr>
              : users.data.map((u) => (
                <tr key={u.id}>
                  <td className="mono">#{u.id}</td>
                  <td>{u.first_name} {u.last_name}</td>
                  <td>{u.email}</td>
                  <td>{u.phone ?? '—'}</td>
                  <td><span className={`badge badge-${u.is_admin ? 'delivered' : 'pending'}`}>{u.is_admin ? 'admin' : 'customer'}</span></td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Admin() {
  useEffect(() => {
    // silent — admin alerts fall back to sound either way
    if (notificationsSupported() && Notification.permission === 'default') void Notification.requestPermission();
  }, []);

  return (
    <div className="admin-page">
      <div className="admin-layout">
        <div>
          <h1>🛠️ Admin Dashboard</h1>
          <p className="subtitle">Fleet status and order management — pulled live from the drone service.</p>
        </div>
        <FleetCard />
        <AuditCard />
        <OrdersCard />
        <UsersCard />
      </div>
    </div>
  );
}

