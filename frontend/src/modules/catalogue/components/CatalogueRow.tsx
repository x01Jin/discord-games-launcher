import { memo } from "react";
import type { CatalogueGame } from "../../../shared/api-client";
import { GameArt } from "../../../shared/components/GameArt";
import { CheckIcon, PlusIcon } from "../../../shared/components/icons";
import { Button, Chip } from "../../../shared/components/primitives";

interface Props {
  game: CatalogueGame;
  index: number;
  selected: boolean;
  onToggle: () => void;
  onAdd: () => void;
  onFocusRow: (index: number) => void;
  rowHeight: number;
}

function CatalogueRowInner({
  game,
  index,
  selected,
  onToggle,
  onAdd,
  onFocusRow,
  rowHeight,
}: Props) {
  return (
    <div
      className={
        "flex items-center gap-3 border-b border-line px-5 transition-colors duration-100 " +
        (game.in_library ? "opacity-60" : "hover:bg-hover")
      }
      style={{ height: rowHeight }}
    >
      <button
        type="button"
        role="checkbox"
        aria-checked={selected}
        aria-label={game.name + (game.in_library ? ", in library" : "")}
        disabled={game.in_library}
        data-row-index={index}
        onClick={onToggle}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            onFocusRow(index + 1);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            onFocusRow(index - 1);
          } else if (event.key === "Enter") {
            event.preventDefault();
            if (game.in_library) onAdd();
            else onToggle();
          } else if (event.key === " ") {
            event.preventDefault();
            onToggle();
          }
        }}
        className="flex min-w-0 flex-1 items-center gap-3 rounded-[4px] text-left focus:outline-none disabled:cursor-default"
      >
        <span
          aria-hidden="true"
          className={
            "flex size-4 shrink-0 items-center justify-center rounded-[3px] border transition-colors " +
            (selected
              ? "border-accent bg-accent text-white"
              : "border-line-strong bg-transparent text-transparent")
          }
        >
          <CheckIcon size={11} />
        </span>
        <GameArt
          name={game.name}
          gameId={game.id}
          iconHash={game.icon_hash}
          size={30}
        />
        <span className="min-w-0 flex-1 truncate-1 text-[13px] font-medium text-ink" title={game.name}>
          {game.name}
        </span>
        <span className="hidden min-w-0 max-w-[340px] shrink-0 gap-1 md:flex">
          {game.win_exes.slice(0, 2).map((exe) => (
            <Chip key={exe} title={exe}>
              {exe.split("/").pop()}
            </Chip>
          ))}
          {game.win_exes.length > 2 ? (
            <Chip title={game.win_exes.slice(2).join(", ")}>
              +{game.win_exes.length - 2}
            </Chip>
          ) : null}
        </span>
      </button>

      <div className="flex w-[104px] shrink-0 justify-end">
        {game.in_library ? (
          <span className="text-[12px] text-success">In library</span>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            icon={<PlusIcon size={12} />}
            onClick={onAdd}
            aria-label={"Add " + game.name + " to library"}
          >
            Add
          </Button>
        )}
      </div>
    </div>
  );
}

export const CatalogueRow = memo(CatalogueRowInner);
