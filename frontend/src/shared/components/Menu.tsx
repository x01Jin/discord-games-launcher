import { useEffect, useLayoutEffect, useRef, useState } from "react";
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
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
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
                : "text-muted hover:bg-accent hover:text-white",
              "disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted",
            ].join(" ")}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>
    </>
  );
}
