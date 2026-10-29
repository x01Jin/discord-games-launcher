import { useState } from "react";
import {
  useLibraryGames,
  useRemoveGame,
  useRemoveGames,
  useRepairLibrary,
  useStopAll,
  useToggleGame,
} from "../hooks/useLibrary";
import { PageHeader, Toolbar } from "../../../shared/components/PageHeader";
import { Dialog } from "../../../shared/components/Dialog";
import {
  Button,
  Checkbox,
  EmptyState,
  Skeleton,
} from "../../../shared/components/primitives";
import {
  LibraryIcon,
  RefreshIcon,
  StopIcon,
  TrashIcon,
  WrenchIcon,
} from "../../../shared/components/icons";
import { formatCount } from "../../../shared/lib/format";
import { useUiStore } from "../../../shared/store/ui-store";
import { LibraryRow } from "./LibraryRow";

export function LibraryPage() {
  const { data, isLoading, isError, refetch, isFetching } = useLibraryGames();
  const toggle = useToggleGame();
  const stopAll = useStopAll();
  const remove = useRemoveGame();
  const removeGames = useRemoveGames();
  const repair = useRepairLibrary();
  const setPage = useUiStore((state) => state.setPage);

  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirmRepair, setConfirmRepair] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [confirmRemoveMany, setConfirmRemoveMany] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const games = data?.games ?? [];
  const running = games.filter((game) => game.is_running).length;
  const backendError = data?.error;

  const present = new Set(games.map((game) => game.game_id));
  const selected = picked.filter((id) => present.has(id));
  const allSelected = games.length > 0 && selected.length === games.length;

  const toggleRow = (id: string) => {
    setPicked((current) =>
      current.includes(id)
        ? current.filter((existing) => existing !== id)
        : [...current, id],
    );
  };

  const startToggle = (gameId: string, isRunning: boolean) => {
    setPendingId(gameId);
    toggle.mutate(
      { id: gameId, running: isRunning },
      { onSettled: () => setPendingId(null) },
    );
  };

  const body = (() => {
    if (isLoading) {
      return (
        <div className="space-y-2 px-5 py-4">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="flex items-center gap-3">
              <Skeleton className="size-9" />
              <Skeleton className="h-3 flex-1" />
            </div>
          ))}
        </div>
      );
    }
    if (isError || backendError) {
      return (
        <EmptyState
          icon={<LibraryIcon size={28} />}
          title="Your library did not load"
          description={backendError ?? "The backend did not answer. Try again."}
          action={
            <Button icon={<RefreshIcon size={13} />} onClick={() => void refetch()}>
              Try again
            </Button>
          }
        />
      );
    }
    if (games.length === 0) {
      return (
        <EmptyState
          icon={<LibraryIcon size={28} />}
          title="Nothing in the library yet"
          description="Add a game from the catalogue."
          action={
            <Button
              icon={<LibraryIcon size={13} />}
              onClick={() => setPage("catalogue")}
            >
              Browse catalogue
            </Button>
          }
        />
      );
    }
    return (
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {games.map((game) => (
          <LibraryRow
            key={game.game_id}
            game={game}
            busy={pendingId === game.game_id}
            selected={selected.includes(game.game_id)}
            onSelect={() => toggleRow(game.game_id)}
            onToggle={() => startToggle(game.game_id, game.is_running)}
            onRemove={() => setConfirmRemove({ id: game.game_id, name: game.name })}
          />
        ))}
      </div>
    );
  })();

  return (
    <section aria-label="Library" className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Library"
        subtitle={
          games.length
            ? formatCount(games.length) +
              " games · " +
              (running ? running + " running" : "none running")
            : "Games you added"
        }
        actions={
          <>
            <Button
              size="sm"
              variant="ghost"
              busy={isFetching && !isLoading}
              icon={<RefreshIcon size={13} />}
              onClick={() => void refetch()}
            >
              Refresh
            </Button>
            <Button
              size="sm"
              variant="ghost"
              icon={<WrenchIcon size={13} />}
              busy={repair.isPending}
              onClick={() => setConfirmRepair(true)}
            >
              Repair
            </Button>
            <Button
              size="sm"
              variant="secondary"
              icon={<StopIcon size={11} />}
              disabled={running === 0}
              busy={stopAll.isPending}
              onClick={() => stopAll.mutate()}
            >
              Stop all
            </Button>
          </>
        }
      />

      {games.length > 0 && !isLoading ? (
        <Toolbar>
          <div className="flex items-center gap-2">
            <Checkbox
              checked={allSelected}
              onChange={() =>
                setPicked(allSelected ? [] : games.map((game) => game.game_id))
              }
              label="Select all"
            />
            <button
              type="button"
              onClick={() =>
                setPicked(allSelected ? [] : games.map((game) => game.game_id))
              }
              className="text-[12px] text-subtle transition-colors hover:text-ink"
            >
              Select all
            </button>
          </div>
          {selected.length > 0 ? (
            <span className="text-[12px] text-muted">
              {selected.length} selected
            </span>
          ) : null}
          <div className="flex-1" />
          {selected.length > 0 ? (
            <>
              <Button
                size="sm"
                variant="danger"
                busy={removeGames.isPending}
                icon={<TrashIcon size={12} />}
                onClick={() => setConfirmRemoveMany(true)}
              >
                Remove {selected.length === 1 ? "game" : "games"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setPicked([])}>
                Clear
              </Button>
            </>
          ) : null}
        </Toolbar>
      ) : null}

      {body}

      <Dialog
        open={confirmRepair}
        title="Repair library?"
        danger
        onClose={() => setConfirmRepair(false)}
        description={
          <>
            Repair removes library entries whose game left the catalogue,
            replaces outdated executable names, recreates missing files, and
            clears stale state.
            <br />
            <span className="font-semibold text-[#ff8f8f]">
              Files are deleted permanently.
            </span>{" "}
            This cannot be undone.
          </>
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmRepair(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              busy={repair.isPending}
              onClick={() => {
                setConfirmRepair(false);
                repair.mutate();
              }}
            >
              Repair library
            </Button>
          </>
        }
      />

      <Dialog
        open={confirmRemoveMany}
        title={
          "Remove " + selected.length + (selected.length === 1 ? " game?" : " games?")
        }
        onClose={() => setConfirmRemoveMany(false)}
        description={
          <>
            {selected.length === 1 ? "The game leaves" : "The games leave"} your
            library and{" "}
            {selected.length === 1 ? "its files are" : "their files are"} deleted.
            Running games are stopped first. You can add them again from the
            catalogue.
          </>
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmRemoveMany(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              busy={removeGames.isPending}
              onClick={() => {
                const ids = selected;
                setConfirmRemoveMany(false);
                setPicked(ids);
                removeGames.mutate(ids);
              }}
            >
              Remove {selected.length === 1 ? "game" : "games"}
            </Button>
          </>
        }
      />

      <Dialog
        open={confirmRemove !== null}
        title={"Remove " + (confirmRemove?.name ?? "") + "?"}
        onClose={() => setConfirmRemove(null)}
        description="The game and its files are deleted. You can add it again from the catalogue."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmRemove(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (confirmRemove) remove.mutate(confirmRemove.id);
                setConfirmRemove(null);
              }}
            >
              Remove game
            </Button>
          </>
        }
      />
    </section>
  );
}
