import { useUiStore } from "../store/ui-store";
import { AlertIcon, CheckIcon, InfoIcon } from "./icons";

const TONE = {
  info: { border: "border-l-accent", icon: <InfoIcon size={15} className="text-accent" /> },
  success: {
    border: "border-l-success",
    icon: <CheckIcon size={15} className="text-success" />,
  },
  error: {
    border: "border-l-danger",
    icon: <AlertIcon size={15} className="text-danger" />,
  },
} as const;

/** Bottom-right stack, matching where desktop apps put transient notices. */
export function Toasts() {
  const toasts = useUiStore((state) => state.toasts);
  const dismiss = useUiStore((state) => state.dismissToast);

  return (
    <div
      aria-live="polite"
      aria-relevant="additions"
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[340px] flex-col gap-2"
    >
      {toasts.map((toast) => {
        const tone = TONE[toast.kind] ?? TONE.info;
        return (
          <div
            key={toast.id}
            role="status"
            style={{ animation: "dcgl-rise 140ms ease-out" }}
            className={
              "pointer-events-auto flex items-start gap-2 rounded-[6px] border border-line-strong border-l-2 bg-[#111214] px-3 py-2.5 shadow-2xl " +
              tone.border
            }
          >
            <span className="pt-px">{tone.icon}</span>
            <p className="min-w-0 flex-1 text-[13px] leading-[18px] text-ink">
              {toast.message}
            </p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="-mr-1 shrink-0 rounded px-1 text-[11px] text-subtle hover:text-ink"
              aria-label="Dismiss"
            >
              Dismiss
            </button>
          </div>
        );
      })}
    </div>
  );
}
