import { useRef, useState } from "react";
import { ContextMenu, GameIcon } from "../../../shared/components";
import type { MenuItem } from "../../../shared/components";
import type { LibraryGame } from "../../../shared/api-client";

interface Props {
  game: LibraryGame;
  onToggle: () => void;
  onRemove: () => void;
}

export function LibraryCard({ game, onToggle, onRemove }: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const clickTimer = useRef<number | null>(null);

  const handleClick = () => {
    if (clickTimer.current) {
      window.clearTimeout(clickTimer.current);
      clickTimer.current = null;
      onToggle();
    } else {
      clickTimer.current = window.setTimeout(() => {
        clickTimer.current = null;
      }, 220);
    }
  };

  const menuItems: MenuItem[] = [
    { label: game.is_running ? "Stop game" : "Start game", action: onToggle },
    {
      label: "Remove from library",
      danger: true,
      action: () => setConfirming(true),
    },
  ];

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-label={`${game.name}, ${game.is_running ? "running" : "stopped"}`}
        title={game.name}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === " " || e.key === "Enter") {
            e.preventDefault();
            onToggle();
          }
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          setMenu({ x: e.clientX, y: e.clientY });
        }}
        className="game-card min-h-28 cursor-pointer rounded-[10px] bg-card p-4 ring-1 ring-transparent hover:ring-white/15"
      >
        <div className="flex items-center gap-2">
          <GameIcon
            gameId={game.game_id}
            iconHash={game.icon_hash}
            name={game.name}
          />
          <span
            aria-hidden="true"
            className={`inline-block h-2 w-2 shrink-0 rounded-full ${game.is_running ? "bg-green-400" : "bg-muted"}`}
          />
          <p
            title={game.name}
            className="truncate-title min-w-0 flex-1 text-sm font-medium text-white"
          >
            {game.name}
          </p>
        </div>
        <p className="mt-1.5 text-xs text-muted">
          {game.is_running ? "Running" : "Stopped"} · {game.process_name}
        </p>
      </div>

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          items={menuItems}
          onClose={() => setMenu(null)}
        />
      )}

      {confirming && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setConfirming(false)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Remove ${game.name}`}
            className="w-80 rounded-xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-base font-semibold text-white">Remove game?</h2>
            <p className="mt-2 text-sm text-muted">
              {game.name} will be removed from your library. You can add it
              again from the catalogue.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded-full px-4 py-1.5 text-xs font-semibold text-muted hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirming(false);
                  onRemove();
                }}
                className="rounded-full bg-red-500/90 px-4 py-1.5 text-xs font-semibold text-white hover:bg-red-500"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
