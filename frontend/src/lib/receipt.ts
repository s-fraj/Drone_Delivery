import type { Order } from './types';

const esc = (s: string | number): string =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

/** Opens a clean, printable receipt in a new tab. */
export function openReceipt(order: Order): void {
  const stops = [order.dropoff_address, ...(order.extra_dropoffs ?? []).map((d) => d.address)];
  const win = window.open('', '_blank');
  if (!win) return;
  win.document.write(`<!doctype html>
<html><head><meta charset="utf-8"><title>Receipt — Order #${order.id}</title>
<style>
  body { font-family: -apple-system, sans-serif; max-width: 480px; margin: 3rem auto; color: #111827; }
  h1 { font-size: 1.3rem; margin-bottom: 0.2rem; }
  .muted { color: #6b7280; font-size: 0.85rem; margin-bottom: 2rem; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb; font-size: 0.9rem; }
  td:last-child { text-align: right; font-weight: 600; }
  .total td { font-size: 1.1rem; font-weight: 800; border-bottom: none; padding-top: 1rem; }
  @media print { button { display: none; } }
</style></head><body>
<h1>🚁 Drovery — Receipt</h1>
<div class="muted">Order #${order.id} — ${esc(new Date(order.created_at).toLocaleString())}</div>
<table>
  <tr><td>Pickup</td><td>${esc(order.pickup_address)}</td></tr>
  ${stops.map((s, i) => `<tr><td>Drop-off${stops.length > 1 ? ' #' + (i + 1) : ''}</td><td>${esc(s)}</td></tr>`).join('')}
  <tr><td>Package weight</td><td>${esc(order.package_weight)} kg</td></tr>
  <tr><td>Payment status</td><td>${esc(order.payment_status)}</td></tr>
  <tr class="total"><td>Total paid</td><td>$${order.price.toFixed(2)}</td></tr>
</table>
<p style="margin-top:2rem"><button onclick="window.print()">🖨️ Print / Save as PDF</button></p>
</body></html>`);
  win.document.close();
}
