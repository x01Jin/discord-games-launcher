import { useEffect } from "react";
import { useAddGames, useCatalogueGames } from "../hooks/useCatalogue";
import type { CatalogueGame } from "../../../shared/api-client";
import { SearchBar } from "../../../shared/components";
import { useDebouncedValue } from "../../../shared/hooks";
import { useUiStore } from "../../../shared/store/ui-store";
import { GameCard } from "./GameCard";

function focusCard(
  container: HTMLElement | null,
  id: string,
  dir: 1 | -1,
): void {
  if (!container) return;
  const cards = [...container.querySelectorAll<HTMLElement>("[data-card-id]")];
  const i = cards.findIndex((c) => c.dataset.cardId === id);
  const next = cards[i + dir];
  next?.focus();
}

export function CataloguePage() {
  const search = useUiStore((s) => s.search);
  const setSearch = useUiStore((s) => s.setSearch);
  const setCatalogueCounts = useUiStore((s) => s.setCatalogueCounts);
  const selected = useUiStore((s) => s.selected);
  const toggleSelected = useUiStore((s) => s.toggleSelected);
  const debounced = useDebouncedValue(search, 250);

  const { data, isLoading, isError, refetch } = useCatalogueGames(debounced);
  const addGames = useAddGames();

  const games: CatalogueGame[] = data?.games ?? [];
  const total: number = data?.total ?? 0;
  const backendError: string | undefined = data?.error;

  useEffect(() => {
    setCatalogueCounts(total, games.length);
  }, [total, games.length, setCatalogueCounts]);

  return (
    <section
      aria-label="Game catalogue"
      className="mx-auto flex h-full min-h-0 w-full max-w-6xl flex-col"
    >
      <div className="shrink-0 bg-ink pt-4">
        <SearchBar value={search} onChange={setSearch} />
      </div>

      <div className="dcgl-scroll min-h-0 flex-1 overflow-y-auto pr-1">
        {isLoading && (
          <p className="mt-10 text-center text-sm text-muted">Loading games…</p>
        )}

        {(isError || backendError) && (
          <div className="mt-10 px-4 text-center">
            <p className="text-sm text-white">
              {backendError ??
                "Could not load the catalogue. Check the backend connection."}
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
          <div className="mt-10 px-4 text-center">
            {debounced ? (
              <>
                <p className="text-sm text-white">
                  No games match “{debounced}”.
                </p>
                <p className="mt-1 text-xs text-muted">
                  Try a different search, or sync the catalogue to refresh the
                  cache.
                </p>
              </>
            ) : (
              <>
                <p className="text-sm text-white">Catalogue is empty.</p>
                <p className="mt-1 text-xs text-muted">
                  Press Sync catalogue to fetch games from Discord.
                </p>
              </>
            )}
          </div>
        )}

        <div
          className="mt-4 grid gap-4 pb-8"
          style={{
            gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          }}
        >
          {games.map((g) => (
            <GameCard
              key={g.id}
              game={g}
              selected={selected.includes(g.id)}
              onToggle={() => toggleSelected(g.id)}
              onAddOne={() => addGames.mutate([g.id])}
              onFocusNext={(dir) =>
                focusCard(
                  document.querySelector(
                    'section[aria-label="Game catalogue"]',
                  ),
                  g.id,
                  dir,
                )
              }
            />
          ))}
        </div>
      </div>

      {selected.length > 0 && (
        <div className="pointer-events-none fixed inset-x-0 bottom-20 z-40 flex justify-center px-4">
          <button
            type="button"
            onClick={() => addGames.mutate(selected)}
            disabled={addGames.isPending}
            className="pointer-events-auto rounded-full bg-peri px-6 py-2.5 text-sm font-semibold uppercase text-ink shadow-xl hover:bg-peri-strong disabled:opacity-60"
          >
            {addGames.isPending
              ? "Adding…"
              : `Add ${selected.length} selected to library`}
          </button>
        </div>
      )}
    </section>
  );
}
