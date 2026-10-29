import type { QuestGame } from "../../../shared/api-client";
import { GameArt } from "../../../shared/components/GameArt";
import {
  ClockIcon,
  OrbIcon,
  PlayIcon,
  StopIcon,
} from "../../../shared/components/icons";
import { Button, Checkbox, Chip, ProgressBar } from "../../../shared/components/primitives";
import { formatPercent, formatProgress, formatTimeLeft } from "../../../shared/lib/format";

interface Props {
  quest: QuestGame;
  busy: boolean;
  selected: boolean;
  selectable: boolean;
  /** The queue is waiting for this video to be credited in Discord. */
  watching?: boolean;
  onSelect: (next: boolean) => void;
  onStart: () => void;
  onStop: () => void;
  onWatch: () => void;
}

const KIND_LABEL: Record<QuestGame["kind"], string> = {
  play: "Play on desktop",
  watch: "Watch video",
  watch_mobile: "Mobile video",
};

export function QuestRow({
  quest,
  busy,
  selected,
  selectable,
  watching = false,
  onSelect,
  onStart,
  onStop,
  onWatch,
}: Props) {
  const showProgress =
    quest.target_seconds > 0 &&
    (quest.enrolled || quest.progress_seconds > 0 || quest.state === "running");
  const urgent =
    quest.state === "ready" &&
    typeof quest.seconds_left === "number" &&
    quest.seconds_left > 0 &&
    quest.seconds_left < 86_400;
  // The title is often the game name too, so only repeat it when it differs.
  const meta =
    [
      quest.kind === "play" ? "" : KIND_LABEL[quest.kind],
      quest.game_name && quest.game_name !== quest.name ? quest.game_name : "",
      quest.process_name,
    ]
      .filter(Boolean)
      .join(" · ") || KIND_LABEL[quest.kind];

  return (
    <div
      className={
        "row-skip flex items-center gap-3 border-b border-line px-5 py-2.5 transition-colors duration-100 " +
        (selected ? "bg-accent/[0.07] hover:bg-accent/[0.1]" : "hover:bg-hover")
      }
    >
      <div className="flex w-4 shrink-0 justify-center">
        {selectable ? (
          <Checkbox
            checked={selected}
            onChange={onSelect}
            label={"Select " + quest.name}
          />
        ) : null}
      </div>

      <GameArt
        name={quest.game_name}
        gameId={quest.application_id}
        iconHash={quest.icon_hash}
        artPath={quest.video_thumbnail ?? quest.tile_url}
        size={40}
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate-1 text-[14px] font-medium text-ink" title={quest.name}>
            {quest.name}
          </p>
          {quest.state === "running" ? <Chip tone="success">Running</Chip> : null}
          {watching ? (
            <Chip tone="accent" title="The queue is waiting for this video in Discord">
              Watching
            </Chip>
          ) : quest.queued ? (
            <Chip tone="accent" title="Starts when the quest ahead of it finishes">
              Queued
            </Chip>
          ) : null}
          {quest.kind === "watch" ? (
            <Chip title="Progress is posted to Discord in the background, no window opens">
              Video
            </Chip>
          ) : null}
          {quest.kind === "watch_mobile" ? (
            <Chip title="Discord lists this video task for mobile. The progress post it accepts is the same, so it still finishes here.">
              Mobile video
            </Chip>
          ) : null}
          {!quest.enrolled && quest.state === "ready" ? (
            <Chip
              tone="warning"
              title="Starting this quest accepts it in Discord first"
            >
              Not accepted
            </Chip>
          ) : null}
        </div>
        <p className="truncate-1 text-[12px] leading-4 text-subtle" title={meta}>
          {meta}
        </p>

        {showProgress ? (
          <div className="mt-1.5 flex max-w-[420px] items-center gap-2">
            <ProgressBar
              value={quest.progress}
              tone={quest.state === "completed" ? "success" : "accent"}
              label={quest.name + " progress"}
            />
            <span className="shrink-0 text-[11px] tabular-nums text-subtle">
              {formatPercent(quest.progress)} ·{" "}
              {formatProgress(quest.progress_seconds, quest.target_seconds)}
            </span>
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {typeof quest.reward.orbs === "number" ? (
          <Chip
            tone="orb"
            icon={<OrbIcon size={11} />}
            title={quest.reward.labels.join(", ") || "Orbs"}
          >
            {quest.reward.orbs.toLocaleString("en-US")}
          </Chip>
        ) : quest.reward.label ? (
          <Chip
            title={quest.reward.labels.join(", ")}
            tone={quest.reward.avatar_decoration ? "accent" : "neutral"}
          >
            <span className="max-w-[170px] truncate-1">{quest.reward.label}</span>
          </Chip>
        ) : null}

        <span
          className={
            "w-[86px] shrink-0 text-right text-[12px] tabular-nums " +
            (urgent ? "text-warning" : "text-subtle")
          }
          title={quest.expires_at ?? undefined}
        >
          {quest.action === "done" ? "—" : formatTimeLeft(quest.seconds_left)}
        </span>

        <div className="flex w-[104px] justify-end">
          <QuestAction
            quest={quest}
            busy={busy}
            onStart={onStart}
            onStop={onStop}
            onWatch={onWatch}
          />
        </div>
      </div>
    </div>
  );
}

function QuestAction({
  quest,
  busy,
  onStart,
  onStop,
  onWatch,
}: Pick<Props, "quest" | "busy" | "onStart" | "onStop" | "onWatch">) {
  switch (quest.action) {
    case "stop":
      return (
        <Button
          variant="secondary"
          size="sm"
          busy={busy}
          icon={<StopIcon size={11} />}
          onClick={onStop}
          title={
            quest.kind === "watch"
              ? "Stop watching this video. The queue moves on to the next quest."
              : "Stop crediting this quest. The queue moves on to the next one."
          }
        >
          Stop
        </Button>
      );
    case "run":
      return (
        <Button variant="primary" size="sm" busy={busy} icon={<PlayIcon size={11} />} onClick={onStart}>
          Run
        </Button>
      );
    case "open":
      return (
        <Button
          variant="success"
          size="sm"
          disabled={quest.queued}
          icon={<PlayIcon size={11} />}
          onClick={onWatch}
          title="Watch this video in the background. Discord credits the progress without opening its quest page."
        >
          Watch
        </Button>
      );
    case "mobile":
      return (
        <span
          className="inline-flex items-center gap-1 text-[12px] text-warning"
          title={
            "This quest only counts on the Discord mobile app, so it cannot be " +
            "finished on this PC."
          }
        >
          <ClockIcon size={11} /> Phone
        </span>
      );
    case "done":
      return (
        <span
          className={
            "text-[12px] " +
            (quest.state === "expired" ? "text-faint" : "text-success")
          }
        >
          {quest.state === "expired" ? "Expired" : "Done"}
        </span>
      );
    default:
      return (
        <span className="text-[12px] text-warning" title="Discord sent no application id for this quest">
          Unsupported
        </span>
      );
  }
}
