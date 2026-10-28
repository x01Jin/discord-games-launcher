import { useState } from "react";
import type { LibraryGame } from "../../../shared/api-client";
import { GameArt } from "../../../shared/components/GameArt";
import { Menu, type MenuItem } from "../../../shared/components/Menu";
import { MoreIcon, PlayIcon, StopIcon, TrashIcon } from "../../../shared/components/icons";
import { Button, IconButton } from "../../../shared/components/primitives";

interface Props {
  game: LibraryGame;
  busy: boolean;
  onToggle: () => void;
  onRemove: () => void;
}

export function LibraryRow({ game, busy, onToggle, onRemove }: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);

  const items: MenuItem[] = [
    {
      label: game.is_running ? "Stop game" : "Start game",
      icon: game.is_running ? <StopIcon size={13} /> : <PlayIcon size={13} />,
      action: onToggle,
    },
    {
      label: "Remove from library",
      icon: <TrashIcon size={13} />,
      danger: true,
      action: onRemove,
    },
  ];

  return (
    <div className="row-skip flex items-center gap-3 border-b border-line px-5 py-2.5 transition-colors duration-100 hover:bg-hover">
      <GameArt name={game.name} gameId={game.game_id} iconHash={game.icon_hash} size={36} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate-1 text-[13px] font-medium text-ink" title={game.name}>
            {game.name}
          </p>
          <span
            className={
              "shrink-0 text-[11px] font-medium " +
              (game.is_running ? "text-success" : "text-faint")
            }
          >
            {game.is_running ? "Running" : "Stopped"}
          </span>
        </div>
        <p className="truncate-1 text-[12px] leading-4 text-subtle" title={game.process_name}>
          {game.process_name}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Button
          size="sm"
          variant={game.is_running ? "secondary" : "primary"}
          busy={busy}
          icon={game.is_running ? <StopIcon size={11} /> : <PlayIcon size={11} />}
          onClick={onToggle}
        >
          {game.is_running ? "Stop" : "Start"}
        </Button>
        <IconButton
          label={"More actions for " + game.name}
          size={26}
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            setMenu({ x: rect.left, y: rect.bottom + 4 });
          }}
        >
          <MoreIcon size={14} />
        </IconButton>
      </div>

      {menu ? (
        <Menu x={menu.x} y={menu.y} items={items} onClose={() => setMenu(null)} />
      ) : null}
    </div>
  );
}
