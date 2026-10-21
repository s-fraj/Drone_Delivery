import { useEffect, type ReactNode } from 'react';

interface Props {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  maxWidth?: number;
  children: ReactNode;
}

export function Modal({ open, title, onClose, maxWidth = 500, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-overlay open" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" style={{ maxWidth }}>
        <div className="modal-hdr">
          <h3>{title}</h3>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
