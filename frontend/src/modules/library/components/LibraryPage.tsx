import { useState } from "react";
import {
  useLibraryGames,
  useRemoveGame,
  useRepairLibrary,
  useStopAll,
  useToggleGame,
} from "../hooks/useLibrary";
import { LibraryCard } from "./LibraryCard";

export function LibraryPage() {
  const { data, isLoading, isError, refetch, isFetching } = useLibraryGames();
  const toggle = useToggleGame();
  const stopAll = useStopAll();
  const remove = useRemoveGame();
  const repair = useRepairLibrary();
  const [confirmingRepair, setConfirmingRepair] = useState(false);

  const games = data?.games ?? [];
  const backendError: string | undefined = data?.error;

  return (
    <section
      aria-label="My library"
      className="mx-auto flex h-full min-h-0 w-full max-w-6xl flex-col"
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-4 bg-ink pt-4">
        <p className="text-xs text-muted">
          {games.length} game{games.length === 1 ? "" : "s"} in library
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded-full bg-card px-4 py-1.5 text-xs font-semibold text-white ring-1 ring-white/10 hover:ring-white/25 disabled:opacity-60"
          >
            {isFetching ? "Refreshing…" : "Refresh"}
          </button>
          <button
            type="button"
            onClick={() => setConfirmingRepair(true)}
            disabled={repair.isPending}
            className="rounded-full bg-card px-4 py-1.5 text-xs font-semibold text-white ring-1 ring-white/10 hover:ring-white/25 disabled:opacity-60"
          >
            {repair.isPending ? "Repairing…" : "Repair"}
          </button>
          <button
            type="button"
            onClick={() => stopAll.mutate()}
            disabled={stopAll.isPending || games.every((g) => !g.is_running)}
            className="rounded-full bg-red-500/90 px-4 py-1.5 text-xs font-semibold text-white hover:bg-red-500 disabled:opacity-50"
          >
            {stopAll.isPending ? "Stopping…" : "Stop all"}
          </button>
        </div>
      </div>

      <div className="dcgl-scroll min-h-0 flex-1 overflow-y-auto pr-1">
        {isLoading && (
          <p className="mt-10 text-center text-sm text-muted">
            Loading library…
          </p>
        )}

        {(isError || backendError) && (
          <div className="mt-10 px-4 text-center">
            <p className="text-sm text-white">
              {backendError ??
                "Could not load your library. Check the backend connection."}
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="mt-3 rounded-full bg-peri px-4 py-1.5 text-xs font-semibold text-ink hover:bg-peri-strong"
            >
              Try again
            </button>
          </div>
        )}

        {!isLoading && !isError && !backendError && games.length === 0 && (
          <div className="mt-10 text-center">
            <p className="text-sm text-white">Your library is empty.</p>
            <p className="mt-1 text-xs text-muted">
              Browse the catalogue and add games to get started.
            </p>
          </div>
        )}

        <div
          className="mt-4 grid gap-4 pb-8"
          style={{
            gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          }}
        >
          {games.map((g) => (
            <LibraryCard
              key={g.game_id}
              game={g}
              onToggle={() =>
                toggle.mutate({ id: g.game_id, running: g.is_running })
              }
              onRemove={() => remove.mutate(g.game_id)}
            />
          ))}
        </div>
      </div>

      {confirmingRepair && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
          onClick={() => setConfirmingRepair(false)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Repair library"
            className="w-96 max-w-full rounded-xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-base font-semibold text-white">
              Repair library?
            </h2>
            <div className="mt-2 space-y-2 text-sm text-muted">
              <p>
                <span className="font-semibold text-red-400">Warning: </span>
                this permanently deletes files. It removes library entries whose
                game left the catalogue (including their executables), replaces
                outdated executables (deleting the superseded files), recreates
                missing ones, and clears stale data.
              </p>
              <p>This cannot be undone.</p>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmingRepair(false)}
                className="rounded-full px-4 py-1.5 text-xs font-semibold text-muted hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={repair.isPending}
                onClick={() => {
                  setConfirmingRepair(false);
                  repair.mutate();
                }}
                className="rounded-full bg-peri px-4 py-1.5 text-xs font-semibold text-ink hover:bg-peri-strong disabled:opacity-60"
              >
                {repair.isPending ? "Repairing…" : "Repair library"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
