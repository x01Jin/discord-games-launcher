import { useUiStore } from "../store/ui-store";

const KIND_STYLES: Record<string, string> = {
  info: "bg-card text-white",
  success: "bg-card text-white border-l-4 border-green-400",
  error: "bg-card-red text-white border-l-4 border-red-400",
};

export function Toasts() {
  const toasts = useUiStore((s) => s.toasts);
  const dismiss = useUiStore((s) => s.dismissToast);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-16 left-1/2 z-50 flex w-full max-w-md -translate-x-1/2 flex-col items-center gap-2 px-4"
    >
      {toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => dismiss(t.id)}
          className={`pointer-events-auto w-full rounded-lg px-4 py-2.5 text-center text-sm shadow-lg ${KIND_STYLES[t.kind]}`}
        >
          {t.message}
        </button>
      ))}
    </div>
  );
}
