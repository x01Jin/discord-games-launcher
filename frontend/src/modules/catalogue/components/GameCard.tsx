import { useRef, useState } from "react";
import { ContextMenu, GameIcon } from "../../../shared/components";
import type { MenuItem } from "../../../shared/components";
import type { CatalogueGame } from "../../../shared/api-client";

interface Props {
  game: CatalogueGame;
  selected: boolean;
  onToggle: () => void;
  onAddOne: () => void;
  onFocusNext: (dir: 1 | -1) => void;
}

export function GameCard({
  game,
  selected,
  onToggle,
  onAddOne,
  onFocusNext,
}: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const clickTimer = useRef<number | null>(null);

  const handleClick = () => {
    // Single click toggles (skip in-library games); double-click adds immediately.
    if (clickTimer.current) {
      window.clearTimeout(clickTimer.current);
      clickTimer.current = null;
      onAddOne();
      return;
    }
    clickTimer.current = window.setTimeout(() => {
      clickTimer.current = null;
      onToggle();
    }, 220);
  };

  const menuItems: MenuItem[] = game.in_library
    ? [{ label: "Already in library", action: () => {} }]
    : [{ label: "Add to library", action: onAddOne }];

  return (
    <>
      <div
        role="checkbox"
        aria-checked={selected}
        aria-label={`${game.name}${game.in_library ? ", in library" : ""}`}
        tabIndex={0}
        title={game.name}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === " " || e.key === "Enter") {
            e.preventDefault();
            onToggle();
          } else if (e.key === "ArrowRight") {
            e.preventDefault();
            onFocusNext(1);
          } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            onFocusNext(-1);
          }
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          setMenu({ x: e.clientX, y: e.clientY });
        }}
        data-card-id={game.id}
        className={`game-card min-h-28 cursor-pointer rounded-[10px] p-4 ${
          selected
            ? "ring-2 ring-peri"
            : "ring-1 ring-transparent hover:ring-white/15"
        } ${game.in_library ? "opacity-70" : ""}`}
      >
        <div className="flex items-center gap-2.5">
          <GameIcon
            gameId={game.id}
            iconHash={game.icon_hash}
            name={game.name}
          />
          <p
            title={game.name}
            className="truncate-title min-w-0 flex-1 text-sm font-medium text-white"
          >
            {game.name}
          </p>
        </div>
        <div className="mt-1.5 flex flex-col gap-0.5">
          {game.win_exes.slice(0, 3).map((exe, i) => (
            <p
              key={i}
              className="truncate-title text-xs text-muted"
              title={exe}
            >
              {exe}
            </p>
          ))}
          {game.win_exes.length > 3 && (
            <p
              className="truncate-title text-xs text-muted"
              title={game.win_exes.slice(3).join(", ")}
            >
              +{game.win_exes.length - 3} more
            </p>
          )}
          {game.in_library && (
            <p className="text-xs text-success">In library</p>
          )}
        </div>
      </div>
      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          items={menuItems}
          onClose={() => setMenu(null)}
        />
      )}
    </>
  );
}
