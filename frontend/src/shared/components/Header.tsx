import { useMutation, useQueryClient } from "@tanstack/react-query";
import logoUrl from "../../assets/dcgl.png";
import { bridge } from "../api-client";
import { useUiStore } from "../store/ui-store";

export function Header() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((s) => s.pushToast);
  const setStatsOpen = useUiStore((s) => s.setStatsOpen);

  const sync = useMutation({
    mutationFn: () => bridge.sync_catalogue(),
    onSuccess: (r) => {
      void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      pushToast(r.message, r.synced ? "success" : "error");
    },
    onError: () =>
      pushToast(
        "Sync failed. Check the backend connection and try again.",
        "error",
      ),
  });

  return (
    <header className="flex items-center justify-between px-6 pt-5">
      <div className="flex items-center gap-3">
        <img
          src={logoUrl}
          alt="Discord Games Launcher"
          className="h-9 w-9 shrink-0"
        />
        <h1 className="text-sm font-semibold uppercase tracking-[0.18em] text-white">
          Discord Games Launcher
        </h1>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          className="rounded-full bg-peri px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-ink hover:bg-peri-strong disabled:opacity-60"
        >
          {sync.isPending ? "Syncing…" : "Sync catalogue"}
        </button>
        <button
          type="button"
          onClick={() => setStatsOpen(true)}
          className="rounded-full bg-peri px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-ink hover:bg-peri-strong"
        >
          Stats
        </button>
      </div>
    </header>
  );
}
