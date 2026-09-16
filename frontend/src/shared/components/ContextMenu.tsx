import { useEffect } from "react";

export interface MenuItem {
  label: string;
  danger?: boolean;
  action: () => void;
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

/** Small right-click menu, positioned at the cursor. */
export function ContextMenu({ x, y, items, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(e) => {
          e.preventDefault();
          onClose();
        }}
      />
      <div
        role="menu"
        style={{ left: x, top: y }}
        className="fixed z-50 min-w-44 overflow-hidden rounded-lg bg-card py-1 shadow-xl ring-1 ring-white/10"
      >
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            role="menuitem"
            autoFocus={items.indexOf(item) === 0}
            onClick={() => {
              item.action();
              onClose();
            }}
            className={`block w-full px-4 py-2 text-left text-sm hover:bg-white/10 ${
              item.danger ? "text-red-300" : "text-white"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
    </>
  );
}
