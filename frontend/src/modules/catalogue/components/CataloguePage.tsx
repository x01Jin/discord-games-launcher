import { useCallback, useEffect, useMemo, useRef } from "react";
import { PageHeader, Toolbar } from "../../../shared/components/PageHeader";
import { SearchField } from "../../../shared/components/SearchField";
import {
  Button,
  EmptyState,
  IconButton,
  Skeleton,
} from "../../../shared/components/primitives";
import { CatalogueIcon, PlusIcon, RefreshIcon } from "../../../shared/components/icons";
import { useDebouncedValue } from "../../../shared/hooks/useDebouncedValue";
import { useVirtualRows } from "../../../shared/hooks/useVirtualRows";
import { formatCount } from "../../../shared/lib/format";
import { useUiStore } from "../../../shared/store/ui-store";
import {
  flattenedGames,
  useAddGames,
  useCatalogueGames,
} from "../hooks/useCatalogue";
import { CatalogueRow } from "./CatalogueRow";

const ROW_HEIGHT = 48;

export function CataloguePage() {
  const search = useUiStore((state) => state.search);
  const setSearch = useUiStore((state) => state.setSearch);
  const selected = useUiStore((state) => state.selected);
  const toggleSelected = useUiStore((state) => state.toggleSelected);
  const clearSelected = useUiStore((state) => state.clearSelected);
  const debounced = useDebouncedValue(search, 220);

  const query = useCatalogueGames(debounced);
  const addGames = useAddGames();

  const games = useMemo(() => flattenedGames(query.data), [query.data]);
  const total = query.data?.pages[0]?.total ?? 0;
  const backendError = query.data?.pages.find((page) => page.error)?.error;
  const filtered = debounced.trim().length > 0;

  const { scroller, start, end, offsetTop, totalHeight } = useVirtualRows(
    games.length,
    ROW_HEIGHT,
  );

  // Fetch the next page when the window approaches the end of what is loaded.
  const requested = useRef(0);
  useEffect(() => {
    if (!query.hasNextPage || query.isFetchingNextPage) return;
    if (end < games.length - 8) return;
    if (requested.current === games.length) return;
    requested.current = games.length;
    void query.fetchNextPage();
  }, [end, games.length, query]);

  const focusRow = useCallback((index: number) => {
    const node = document.querySelector<HTMLElement>(
      '[data-row-index="' + index + '"]',
    );
    if (!node) return;
    node.focus();
    node.scrollIntoView({ block: "nearest" });
  }, []);

  const body = (() => {
    if (query.isLoading) {
      return (
        <div className="space-y-2 px-5 py-4">
          {Array.from({ length: 8 }, (_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="size-[30px]" />
              <Skeleton className="h-3 flex-1" />
            </div>
          ))}
        </div>
      );
    }
    if (query.isError || backendError) {
      return (
        <EmptyState
          icon={<CatalogueIcon size={28} />}
          title="The catalogue did not load"
          description={backendError ?? "The backend did not answer. Try again."}
          action={
            <Button icon={<RefreshIcon size={13} />} onClick={() => void query.refetch()}>
              Try again
            </Button>
          }
        />
      );
    }
    if (games.length === 0) {
      return (
        <EmptyState
          icon={<CatalogueIcon size={28} />}
          title={filtered ? "No games match that search" : "The catalogue is empty"}
          description={
            filtered
              ? "Try fewer words, or part of the executable name."
              : "Sync the catalogue to pull Discord's detectable games database."
          }
          action={
            filtered ? (
              <Button onClick={() => setSearch("")}>Clear search</Button>
            ) : (
              <Button icon={<RefreshIcon size={13} />} onClick={() => void query.refetch()}>
                Reload
              </Button>
            )
          }
        />
      );
    }
    return (
      <div ref={scroller} className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div style={{ height: totalHeight, position: "relative" }}>
          <div
            style={{
              transform: "translateY(" + offsetTop + "px)",
              position: "absolute",
              inset: "0 0 auto 0",
            }}
          >
            {games.slice(start, end).map((game, offset) => {
              const index = start + offset;
              return (
                <CatalogueRow
                  key={game.id}
                  game={game}
                  index={index}
                  rowHeight={ROW_HEIGHT}
                  selected={selected.includes(game.id)}
                  onToggle={() => toggleSelected(game.id)}
                  onAdd={() => addGames.mutate([game.id])}
                  onFocusRow={focusRow}
                />
              );
            })}
          </div>
        </div>
        {query.isFetchingNextPage ? (
          <p className="py-3 text-center text-[12px] text-subtle">Loading more…</p>
        ) : null}
      </div>
    );
  })();

  return (
    <section aria-label="Game catalogue" className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Catalogue"
        subtitle={
          filtered
            ? formatCount(games.length) + " matches"
            : formatCount(total) + " games Discord can detect"
        }
        actions={
          <IconButton label="Reload catalogue" onClick={() => void query.refetch()}>
            <RefreshIcon size={15} />
          </IconButton>
        }
      />

      <Toolbar>
        <div className="max-w-[420px] flex-1">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="Search by game or executable"
          />
        </div>
        <div className="flex-1" />
        {selected.length > 0 ? (
          <>
            <span className="text-[12px] text-muted">
              {selected.length} selected
            </span>
            <Button
              variant="primary"
              size="sm"
              busy={addGames.isPending}
              icon={<PlusIcon size={12} />}
              onClick={() => addGames.mutate(selected)}
            >
              Add {selected.length === 1 ? "game" : "games"}
            </Button>
            <Button variant="ghost" size="sm" onClick={clearSelected}>
              Clear
            </Button>
          </>
        ) : (
          <span className="text-[12px] text-subtle">
            Select rows to add several at once
          </span>
        )}
      </Toolbar>

      {body}
    </section>
  );
}
