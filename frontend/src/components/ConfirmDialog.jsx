import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * A modal confirmation for an action that cannot be undone.
 *
 * Focus moves to Cancel when it opens (the safe choice), Escape cancels,
 * Tab stays inside the dialog, and focus returns to the button that opened
 * it when it closes. It is rendered at the end of <body>, so no animated or
 * blurred ancestor can confine the full-screen backdrop.
 */
export default function ConfirmDialog({
  title,
  children,
  confirmLabel,
  busyLabel = 'Working…',
  busy = false,
  error = null,
  onConfirm,
  onCancel,
}) {
  const titleId = useId();
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    const opener = document.activeElement;
    cancelRef.current?.focus();
    return () => opener?.focus?.();
  }, []);

  function handleKeyDown(event) {
    if (event.key === 'Escape' && !busy) {
      event.stopPropagation();
      onCancel();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = dialogRef.current.querySelectorAll('button:not(:disabled)');
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div className="dialog-backdrop" onMouseDown={() => !busy && onCancel()}>
      <div
        ref={dialogRef}
        className="dialog card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleKeyDown}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>{title}</h2>
        <div className="dialog-body">{children}</div>
        {error && <p className="alert alert-error">{error}</p>}
        <div className="dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="button button-quiet"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button type="button" className="button button-danger" onClick={onConfirm} disabled={busy}>
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
