import type { ReactNode } from 'react';
import { prettyStatus } from '@/lib/labels';

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return <span className={`badge badge-${status}${className ? ' ' + className : ''}`}>{prettyStatus(status)}</span>;
}

export function Empty({ icon, children }: { icon?: string; children: ReactNode }) {
  return (
    <div className="empty">
      {icon && <div className="ei">{icon}</div>}
      <p>{children}</p>
    </div>
  );
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return <div className="error-msg show">{children}</div>;
}
