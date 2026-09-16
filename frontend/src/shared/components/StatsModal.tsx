import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { bridge } from "../api-client";
import { useUiStore } from "../store/ui-store";

function format(n: number): string {
  return n.toLocaleString("en-US");
}

export function StatsModal() {
  const open = useUiStore((s) => s.statsOpen);
  const setOpen = useUiStore((s) => s.setStatsOpen);
  const { data } = useQuery({
    queryKey: ["stats"],
    queryFn: () => bridge.get_stats(),
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Stats"
        className="w-80 rounded-xl bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Stats</h2>
          <button
            type="button"
            aria-label="Close stats"
            onClick={() => setOpen(false)}
            className="rounded p-1 text-muted hover:text-white"
          >
            ✕
          </button>
        </div>
        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Games in cache</dt>
            <dd className="font-semibold text-white">
              {data ? format(data.cached_games) : "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Games without Windows executable</dt>
            <dd className="font-semibold text-white">
              {data ? format(data.games_no_win_exes) : "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Games in library</dt>
            <dd className="font-semibold text-white">
              {data ? format(data.library_games) : "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Running now</dt>
            <dd className="font-semibold text-white">
              {data ? format(data.running_processes) : "—"}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
