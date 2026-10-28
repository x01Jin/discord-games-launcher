import { useEffect, useRef, type ReactNode } from "react";
import { CloseIcon } from "./icons";
import { IconButton } from "./primitives";

interface Props {
  open: boolean;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  width?: number;
  danger?: boolean;
}

/**
 * Modal dialog. Escape closes, the backdrop closes, and focus moves to the
 * first control so a keyboard user is never left behind the overlay.
 */
export function Dialog({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  width = 420,
  danger = false,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    const previous = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
      style={{ animation: "dcgl-fade-in 120ms ease-out" }}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        style={{ width, animation: "dcgl-rise 140ms ease-out" }}
        className="max-w-full rounded-[8px] bg-raised shadow-2xl outline-none"
      >
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <h2
            className={
              "text-[16px] font-semibold " + (danger ? "text-[#ff8f8f]" : "text-ink")
            }
          >
            {title}
          </h2>
          <IconButton label="Close" onClick={onClose} size={26}>
            <CloseIcon size={14} />
          </IconButton>
        </div>
        {description ? (
          <div className="px-5 pt-2 text-[13px] leading-5 text-muted">{description}</div>
        ) : null}
        {children ? <div className="px-5 pt-3">{children}</div> : null}
        {footer ? (
          <div className="flex justify-end gap-2 px-5 pb-5 pt-5">{footer}</div>
        ) : (
          <div className="h-5" />
        )}
      </div>
    </div>
  );
}
