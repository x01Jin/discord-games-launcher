import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

export interface MenuItem {
  label: string;
  icon?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
  action: () => void;
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

/**
 * Cursor-anchored menu. It flips against the viewport edges so a click near
 * the bottom or right of the window does not open a menu that runs off it.
 */
export function Menu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: x, top: y });

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const { width, height } = node.getBoundingClientRect();
    const margin = 8;
    const left = Math.min(x, window.innerWidth - width - margin);
    const top =
      y + height + margin > window.innerHeight ? Math.max(margin, y - height) : y;
    setPosition({ left: Math.max(margin, left), top });
  }, [x, y]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
      const buttons = Array.from(
        ref.current?.querySelectorAll<HTMLButtonElement>(
          "button:not([disabled])",
        ) ?? [],
      );
      if (buttons.length === 0) return;
      event.preventDefault();
      const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? buttons.length - 1
            : event.key === "ArrowDown"
              ? (current + 1) % buttons.length
              : (current - 1 + buttons.length) % buttons.length;
      buttons[next]?.focus();
    };
    const opener = document.activeElement as HTMLElement | null;
    window.addEventListener("keydown", onKey);
    ref.current
      ?.querySelector<HTMLButtonElement>("button:not([disabled])")
      ?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      // Give focus back to the button that opened the menu, unless the chosen
      // item opened something else that already took it.
      if (opener?.isConnected && document.activeElement === document.body) {
        opener.focus();
      }
    };
  }, [onClose]);

  // Rendered at the document root: list rows use content-visibility, which
  // clips anything fixed positioned inside them.
  return createPortal(
    <>
      <div
        className="fixed inset-0 z-40"
        role="presentation"
        onClick={onClose}
        onContextMenu={(event) => {
          event.preventDefault();
          onClose();
        }}
      />
      <div
        ref={ref}
        role="menu"
        style={{ left: position.left, top: position.top, animation: "dcgl-fade-in 90ms ease-out" }}
        className="fixed z-50 min-w-[190px] overflow-hidden rounded-[6px] border border-line-strong bg-[#111214] py-1 shadow-2xl"
      >
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            onClick={() => {
              item.action();
              onClose();
            }}
            className={[
              "flex w-full items-center gap-2 px-3 py-[7px] text-left text-[13px]",
              item.danger
                ? "text-[#ff8f8f] hover:bg-danger hover:text-white"
                : "text-muted hover:bg-hover hover:text-ink",
              "disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted",
            ].join(" ")}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>
    </>,
    document.body,
  );
}
