import { useMemo, useState } from "react";
import type { QuestGame } from "../../../shared/api-client";
import { GameArt } from "../../../shared/components/GameArt";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CloseIcon,
  OrbIcon,
  PlayIcon,
  RefreshIcon,
  TrashIcon,
} from "../../../shared/components/icons";
import { PageHeader } from "../../../shared/components/PageHeader";
import {
  Button,
  Chip,
  EmptyState,
  IconButton,
  Skeleton,
} from "../../../shared/components/primitives";
import {
  useClearQuestQueue,
  useQuests,
  useRemoveFromQuestQueue,
  useReorderQuestQueue,
  useStopQuest,
} from "../../../shared/hooks/useQuests";
import { formatCount, formatPercent, formatProgress } from "../../../shared/lib/format";
import { useUiStore } from "../../../shared/store/ui-store";
import { QuestRow } from "../../quests/components/QuestRow";

/** Stable empty list so the memos below do not re-run on every render. */
const NO_QUESTS: QuestGame[] = [];

const noop = () => undefined;

/**
 * Everything that is already moving: the game session Discord is crediting,
 * the video being watched in the background, and the queue that follows them.
 * The queue is ordered by hand here, because Discord only credits one game at
 * a time and the order decides which quest is next.
 */
export function RunningPage() {
  const { data, isLoading, isFetching, refetch } = useQuests();
  const stopQuest = useStopQuest();
  const clearQueue = useClearQuestQueue();
  const reorder = useReorderQuestQueue();
  const removeItem = useRemoveFromQuestQueue();
  const setPage = useUiStore((state) => state.setPage);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const quests = data?.quests ?? NO_QUESTS;
  const queue = data?.queue;
  const watchingId = queue?.watching ?? null;
  const connected = Boolean(data?.connected);

  const byId = useMemo(
    () => new Map(quests.map((quest) => [quest.id, quest] as const)),
    [quests],
  );

  // queue.ids starts with the video in flight, when there is one; that one is
  // already moving and belongs to "Now", not to "Up next".
  const pending = useMemo(
    () =>
      (queue?.ids ?? [])
        .filter((id) => id !== watchingId)
        .map((id) => byId.get(id))
        .filter((quest): quest is QuestGame => quest !== undefined),
    [queue?.ids, watchingId, byId],
  );

  const watching = watchingId ? (byId.get(watchingId) ?? null) : null;

  // A video in flight is a "running" entry in Discord's payload, but it is not a
  // game session; counting it twice reads as "1 running · 1 video" with no game.
  const games = useMemo(
    () => quests.filter((quest) => quest.state === "running" && quest.id !== watchingId),
    [quests, watchingId],
  );

  // One play session at a time, so the subtitle counts sessions, not rows.
  const runningGames = games.length;

  const running = useMemo(
    () => (watching ? [watching, ...games] : games),
    [watching, games],
  );

  const queueBusy = reorder.isPending || removeItem.isPending;
  const nothingMoving = running.length === 0 && pending.length === 0;

  // Videos and games run in their own lane, so each list moves on its own.
  // Both lanes stay on screen even when one is empty: the two are independent,
  // and hiding the empty one makes the queue look shorter than it is.
  const lanes = [
    {
      key: "watch",
      label: "Videos",
      empty: "No videos queued.",
      items: pending.filter((q) => q.kind === "watch"),
    },
    {
      key: "play",
      label: "Games",
      empty: "No games queued.",
      items: pending.filter((q) => q.kind === "play"),
    },
  ];

  const move = (lane: QuestGame[], index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= lane.length) return;
    const order = lane.map((quest) => quest.id);
    const moved = order[index];
    order[index] = order[target];
    order[target] = moved;
    const rest = pending
      .filter((quest) => !order.includes(quest.id))
      .map((quest) => quest.id);
    reorder.mutate([...order, ...rest]);
  };

  const subtitle = connected
    ? [
        runningGames ? runningGames + " running" : null,
        watching ? "1 video" : null,
        pending.length ? pending.length + " queued" : null,
      ]
        .filter(Boolean)
        .join(" · ") || "Nothing is running right now"
    : "Waiting for the Discord client";

  return (
    <section aria-label="Running" className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Running"
        subtitle={subtitle}
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              busy={isFetching && !isLoading}
              icon={<RefreshIcon size={13} />}
              onClick={() => void refetch()}
            >
              Refresh
            </Button>
            {pending.length > 0 || watching ? (
              <Button
                size="sm"
                variant="ghost"
                busy={clearQueue.isPending}
                icon={<TrashIcon size={12} />}
                onClick={() => clearQueue.mutate()}
                title="Stop the queue and the video, if one is being watched. A running game keeps running until you stop it."
              >
                Clear queue
              </Button>
            ) : null}
          </div>
        }
      />

      {!connected ? (
        isLoading ? (
          <div className="space-y-3 px-5 py-6">
            {[0, 1, 2].map((row) => (
              <Skeleton key={row} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<PlayIcon size={22} />}
            title="Discord is not connected"
            description="Start or connect the client on the Quests page, then come back here to see what is running."
            action={<Button onClick={() => setPage("quests")}>Open Quests</Button>}
          />
        )
      ) : nothingMoving ? (
        <EmptyState
          icon={<PlayIcon size={22} />}
          title="Nothing is running"
          description="Pick quests on the Quests page and press Start selected, or press Run on one row. Games and videos show up here together with the queue that follows them."
          action={<Button onClick={() => setPage("quests")}>Open Quests</Button>}
        />
      ) : (
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
          {running.length > 0 ? (
            <>
              <div className="flex items-baseline gap-2 px-5 pt-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.02em] text-subtle">
                  Now
                </p>
                <span className="text-[11px] text-subtle">
                  {running.length} active
                </span>
              </div>
              {running.map((quest) => (
                <QuestRow
                  key={quest.id}
                  quest={quest}
                  selectable={false}
                  selected={false}
                  watching={quest.id === watchingId}
                  busy={pendingId === quest.id}
                  onSelect={noop}
                  onStart={noop}
                  onStop={() => {
                    setPendingId(quest.id);
                    stopQuest.mutate(quest.id, {
                      onSettled: () => setPendingId(null),
                    });
                  }}
                  onWatch={noop}
                  onClaim={noop}
                />
              ))}
            </>
          ) : null}

          <div className="flex items-baseline gap-2 px-5 pt-4">
            <p className="text-[11px] font-bold uppercase tracking-[0.02em] text-subtle">
              Up next
            </p>
            <span className="text-[11px] text-subtle">
              {pending.length ? pending.length + " waiting" : "empty"}
            </span>
          </div>

          {pending.length === 0 ? (
            <p className="px-5 py-3 text-[12px] text-subtle">
              The queue is empty. Select quests on the Quests page to line them
              up here.
            </p>
          ) : (
            <>
              <p className="px-5 pb-2 text-[11px] text-subtle">
                Each lane runs top to bottom on its own. A video starts while a
                game keeps running.
              </p>
              <div className="grid grid-cols-2 items-start gap-4 px-5 pb-6">
                {lanes.map((lane) => (
                  <div
                    key={lane.key}
                    className="min-w-0 overflow-hidden rounded-md border border-line bg-raised/40"
                  >
                    <div className="flex items-baseline gap-2 border-b border-line px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-subtle">
                        {lane.label}
                      </p>
                      <span className="text-[11px] text-subtle">
                        {lane.items.length}
                      </span>
                    </div>
                    {lane.items.length === 0 ? (
                      <p className="px-3 py-3 text-[11px] text-subtle">{lane.empty}</p>
                    ) : (
                      lane.items.map((quest, index) => (
                        <QueueRow
                          key={quest.id}
                          quest={quest}
                          index={index}
                          first={index === 0}
                          last={index === lane.items.length - 1}
                          busy={queueBusy}
                          onMove={(delta) => move(lane.items, index, delta)}
                          onRemove={() => removeItem.mutate(quest.id)}
                        />
                      ))
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}

/** One waiting quest: its place in line, what it is, and the controls. */
function QueueRow({
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
