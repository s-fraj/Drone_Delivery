import { useEffect, useRef } from 'react';
import { alertsPref, desktopNotify, playTone } from '@/lib/alerts';
import { useToast } from '@/components/Toast';
import type { Order, OrderStatus } from '@/lib/types';

const MESSAGES: Partial<Record<OrderStatus, (id: number) => string>> = {
  delivered: (id) => `✅ Order #${id} delivered!`,
  cancelled: (id) => `⚠️ Order #${id} was cancelled.`,
};

/** Beep + toast (+ desktop notification if enabled) on delivered/cancelled transitions. */
export function useStatusAlerts(orders: Order[] | undefined): void {
  const previous = useRef<Map<number, OrderStatus>>(new Map());
  const toast = useToast();

  useEffect(() => {
    if (!orders) return;
    for (const o of orders) {
      const prev = previous.current.get(o.id);
      const msg = MESSAGES[o.status];
      if (prev !== undefined && prev !== o.status && msg) {
        const text = msg(o.id);
        playTone('sine', 880, 0.6, 0.15);
        toast(text);
        if (alertsPref.get()) desktopNotify('Drovery', text);
      }
      previous.current.set(o.id, o.status);
    }
  }, [orders, toast]);
}
