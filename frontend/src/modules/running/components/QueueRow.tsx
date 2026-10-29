import type { QuestGame } from "../../../shared/api-client";
import { GameArt } from "../../../shared/components/GameArt";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CloseIcon,
  OrbIcon,
} from "../../../shared/components/icons";
import { Chip, IconButton } from "../../../shared/components/primitives";
import { formatCount, formatPercent, formatProgress } from "../../../shared/lib/format";

export function QueueRow({
  quest,
  index,
  first,
  last,
  busy,
  onMove,
  onRemove,
}: {
  quest: QuestGame;
  index: number;
  first: boolean;
  last: boolean;
  busy: boolean;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  return (
    <div className="row-skip flex items-center gap-2 border-b border-line px-3 py-2 transition-colors duration-100 last:border-b-0 hover:bg-hover">
      <span className="w-4 shrink-0 text-right text-[11px] tabular-nums text-subtle">
        {index + 1}
      </span>
      <GameArt
        name={quest.game_name}
        gameId={quest.application_id}
        iconHash={quest.icon_hash}
        artPath={quest.video_thumbnail ?? quest.tile_url}
        size={28}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate-1 text-[13px] font-medium text-ink" title={quest.name}>
          {quest.name}
        </p>
        <p className="truncate-1 text-[11px] text-subtle">
          {quest.kind === "watch"
            ? "Video · credited in the background"
            : "Play · " + quest.game_name}
        </p>
      </div>

      {typeof quest.reward.orbs === "number" ? (
        <Chip
          tone="orb"
          icon={<OrbIcon size={10} />}
          title={quest.reward.labels.join(", ") || "Orbs"}
        >
          {formatCount(quest.reward.orbs)}
        </Chip>
      ) : null}

      {quest.target_seconds > 0 ? (
        <span
          className="w-10 shrink-0 text-right text-[11px] tabular-nums text-subtle"
          title={
            quest.progress_seconds > 0
              ? formatPercent(quest.progress) + " complete"
              : formatProgress(0, quest.target_seconds)
          }
        >
          {formatPercent(quest.progress)}
        </span>
      ) : null}

      <div className="flex shrink-0 items-center gap-0.5">
        <IconButton
          label={"Move " + quest.name + " up"}
          size={26}
          disabled={first || busy}
          onClick={() => onMove(-1)}
        >
          <ArrowUpIcon size={13} />
        </IconButton>
        <IconButton
          label={"Move " + quest.name + " down"}
          size={26}
          disabled={last || busy}
          onClick={() => onMove(1)}
        >
          <ArrowDownIcon size={13} />
        </IconButton>
        <IconButton
          label={"Remove " + quest.name + " from the queue"}
          size={26}
          disabled={busy}
          onClick={onRemove}
        >
          <CloseIcon size={13} />
        </IconButton>
      </div>
    </div>
  );
}
