import { useMemo, useRef, useState } from "react";
import type { QuestGame, QuestReward } from "../../../shared/api-client";
import {
  CheckIcon,
  ChevronDownIcon,
  OrbIcon,
  RefreshIcon,
  TrashIcon,
  WrenchIcon,
} from "../../../shared/components/icons";
import { Menu } from "../../../shared/components/Menu";
import { PageHeader, Toolbar } from "../../../shared/components/PageHeader";
import {
  Button,
  Checkbox,
  EmptyState,
  Skeleton,
  Switch,
} from "../../../shared/components/primitives";
import {
  useClaimQuest,
  useClearQuestQueue,
  useConnectDiscord,
  useDisableSilentMode,
  useEnableSilentMode,
  useQuests,
  useSilentMode,
  useStartDiscord,
  useSkipQuestWatch,
  useStartQuest,
  useStartQuestQueue,
  useStopQuest,
} from "../../../shared/hooks/useQuests";
import { useUiStore } from "../../../shared/store/ui-store";
import { QuestConnectPanel } from "./QuestConnectPanel";
import { QuestRow } from "./QuestRow";

type KindFilter = "all" | "play" | "watch";
type RewardFilter = "all" | "orbs" | "decoration" | "in_game";
type Sort = "suggested" | "expiring" | "orbs" | "progress";

const KIND_FILTERS: { id: KindFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "play", label: "Play" },
  { id: "watch", label: "Watch" },
];

const REWARD_FILTERS: { id: RewardFilter; label: string }[] = [
  { id: "all", label: "All rewards" },
  { id: "orbs", label: "Orbs" },
  { id: "decoration", label: "Avatar decoration" },
  { id: "in_game", label: "In-game item" },
];

const SORTS: { id: Sort; label: string }[] = [
  { id: "suggested", label: "Suggested" },
  { id: "expiring", label: "Expiring soon" },
  { id: "orbs", label: "Most orbs" },
  { id: "progress", label: "Most progress" },
];

const REWARD_FILTER_LABEL: Record<RewardFilter, string> = {
  all: "All rewards",
  orbs: "Orbs",
  decoration: "Avatar decoration",
  in_game: "In-game item",
};

/** Stable empty list so the memos below do not re-run on every render. */
const NO_QUESTS: QuestGame[] = [];

/**
 * What the queue can take: play quests, which run as a faked game process, and
 * video quests, which are credited by progress posts. Unaccepted quests are
 * accepted by the queue itself, so enrollment state does not exclude one.
 */
function isQueuable(quest: QuestGame) {
  if (quest.queued) return false;
  if (quest.kind === "play") return quest.action === "run";
  if (quest.kind === "watch" || quest.kind === "watch_mobile") {
    return quest.action === "open";
  }
  return false;
}

function matchesReward(reward: QuestReward, filter: RewardFilter) {
  if (filter === "orbs") return typeof reward.orbs === "number";
  if (filter === "decoration") return reward.avatar_decoration;
  if (filter === "in_game") return reward.in_game;
  return true;
}

function sortQuests(quests: QuestGame[], sort: Sort) {
  if (sort === "suggested") return quests;
  const copy = [...quests];
  if (sort === "expiring") {
    copy.sort((a, b) => {
      const left = a.seconds_left ?? Number.MAX_SAFE_INTEGER;
      const right = b.seconds_left ?? Number.MAX_SAFE_INTEGER;
      return left - right;
    });
  } else if (sort === "orbs") {
    copy.sort((a, b) => (b.reward.orbs ?? -1) - (a.reward.orbs ?? -1));
  } else {
    copy.sort((a, b) => b.progress - a.progress);
  }
  return copy;
}

export function QuestsPage() {
  const { data, isLoading, isFetching, isError, refetch } = useQuests();
  const connect = useConnectDiscord();
  const startDiscord = useStartDiscord();
  const { data: silent } = useSilentMode();
  const enableSilent = useEnableSilentMode();
  const disableSilent = useDisableSilentMode();
  const startQuest = useStartQuest();
  const stopQuest = useStopQuest();
  const claimQuest = useClaimQuest();
  const startQueue = useStartQuestQueue();
  const clearQueue = useClearQuestQueue();
  const skipWatch = useSkipQuestWatch();
  const showFinished = useUiStore((state) => state.showFinished);
  const setShowFinished = useUiStore((state) => state.setShowFinished);
  const [kind, setKind] = useState<KindFilter>("all");
  const [reward, setReward] = useState<RewardFilter>("all");
  const [sort, setSort] = useState<Sort>("suggested");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pendingId, setPendingId] = useState<string | null>(null);

  const quests = data?.quests ?? NO_QUESTS;
  const queue = data?.queue;
  const queueIds = queue?.ids ?? [];
  const watching = queue?.watching
    ? (quests.find((quest) => quest.id === queue.watching) ?? null)
    : null;

  const counts = useMemo(() => {
    const tally = { open: 0, running: 0, finished: 0, claimable: 0 };
    for (const quest of quests) {
      if (quest.state === "running") tally.running += 1;
      if (quest.action === "done") {
        tally.finished += 1;
      } else if (quest.action === "claim") {
        // Finished, but the reward is still on the table.
        tally.finished += 1;
        tally.claimable += 1;
      } else {
        tally.open += 1;
      }
    }
    return tally;
  }, [quests]);

  const visible = useMemo(() => {
    const filtered = quests.filter((quest) => {
      const done = quest.action === "done";
      if (!showFinished && done) return false;
      if (kind === "play" && quest.kind !== "play") return false;
      if (kind === "watch" && quest.kind === "play") return false;
      return matchesReward(quest.reward, reward);
    });
    return sortQuests(filtered, sort);
  }, [quests, showFinished, kind, reward, sort]);

  const runnable = useMemo(() => visible.filter(isQueuable), [visible]);

  // Derive the live selection during render: a quest can finish or leave
  // Discord's list between polls, and a stale id must never be sent back.
  const selectedLive = useMemo(() => {
    if (selected.size === 0) return selected;
    const live = new Set(runnable.map((quest) => quest.id));
    return new Set([...selected].filter((id) => live.has(id)));
  }, [selected, runnable]);

  const allSelected =
    runnable.length > 0 && runnable.every((quest) => selectedLive.has(quest.id));
  const selectedOrdered = visible
    .filter((quest) => selectedLive.has(quest.id) && isQueuable(quest))
    .map((quest) => quest.id);

  const toggleSelected = (questId: string, next: boolean) => {
    setSelected((current) => {
      const copy = new Set(current);
      if (next) copy.add(questId);
      else copy.delete(questId);
      return copy;
    });
  };

  const connected = Boolean(data?.connected);

  const subtitle = connected
    ? [
        counts.open + " open",
        counts.running ? counts.running + " running" : null,
        queueIds.length ? queueIds.length + " queued" : null,
        counts.claimable ? counts.claimable + " to claim" : null,
        counts.finished ? counts.finished + " finished" : null,
      ]
        .filter(Boolean)
        .join(" · ")
    : "Waiting for the Discord client";

  const withPending = (quest: QuestGame, action: () => void) => {
    setPendingId(quest.id);
    action();
  };

  return (
    <section aria-label="Quests" className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Quests"
        subtitle={subtitle}
        actions={
          <div className="flex items-center gap-2">
            {typeof data?.orbs === "number" ? (
              <span
                className="inline-flex items-center gap-1.5 rounded-[4px] bg-white/[0.05] px-2 py-1 text-[12px] font-semibold tabular-nums text-[#f5c451]"
                title="Orb balance in your Discord account"
              >
                <OrbIcon size={12} />
                {data.orbs.toLocaleString("en-US")}
                <span className="font-normal text-subtle">orbs</span>
              </span>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              busy={isFetching && !isLoading}
              icon={<RefreshIcon size={13} />}
              onClick={() => void refetch()}
            >
              Refresh
            </Button>
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
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            <QuestConnectPanel
              status={data?.status}
              silent={silent}
              error={isError ? "The backend did not answer." : (data?.error ?? null)}
              connecting={connect.isPending || startDiscord.isPending}
              starting={startDiscord.isPending}
              disabling={disableSilent.isPending}
              canStart={Boolean(data?.status?.installed && !data?.status?.running)}
              onConnect={() => connect.mutate()}
              onStartDiscord={() => startDiscord.mutate()}
              onRefresh={() => void refetch()}
              onDisableSilent={() => disableSilent.mutate()}
            />
          </div>
        )
      ) : (
        <>
          <Toolbar>
            <div className="flex items-center gap-1" role="group" aria-label="Quest type">
              {KIND_FILTERS.map((entry) => {
                const active = kind === entry.id;
                return (
                  <button
                    key={entry.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setKind(entry.id)}
                    className={
                      "h-6 rounded-[4px] px-2 text-[12px] font-medium transition-colors " +
                      (active
                        ? "bg-active text-ink"
                        : "text-subtle hover:bg-hover hover:text-ink")
                    }
                  >
                    {entry.label}
                  </button>
                );
              })}
            </div>

            <span className="h-4 w-px bg-line-strong" />

            <MenuButton
              label="Filter"
              value={REWARD_FILTER_LABEL[reward]}
              active={reward !== "all"}
              options={REWARD_FILTERS.map((entry) => ({
                label: entry.label,
                active: reward === entry.id,
                action: () => setReward(entry.id),
              }))}
            />

            <MenuButton
              label="Sort"
              value={SORTS.find((entry) => entry.id === sort)?.label ?? "Suggested"}
              active={sort !== "suggested"}
              options={SORTS.map((entry) => ({
                label: entry.label,
                active: sort === entry.id,
                action: () => setSort(entry.id),
              }))}
            />

            <span className="text-[12px] text-subtle">
              {visible.length} shown
              {quests.length > visible.length ? " of " + quests.length : ""}
            </span>

            <div className="flex-1" />

            {silent && !silent.enabled ? (
              <Button
                size="sm"
                variant="ghost"
                busy={enableSilent.isPending}
                icon={<WrenchIcon size={12} />}
                title="Add the local endpoint to the Discord shortcuts so future launches connect on their own. No restart needed."
                onClick={() => enableSilent.mutate()}
              >
                Set up silent start
              </Button>
            ) : null}

            <Switch
              checked={showFinished}
              onChange={setShowFinished}
              label="Show finished"
            />
          </Toolbar>

          {(runnable.length > 0 || queueIds.length > 0) && (
            <div className="flex items-center gap-3 border-b border-line bg-base/40 px-5 py-1.5">
              {runnable.length > 0 ? (
                <>
                  <Checkbox
                    checked={allSelected}
                    onChange={(next) =>
                      setSelected(
                        next ? new Set(runnable.map((quest) => quest.id)) : new Set(),
                      )
                    }
                    label={allSelected ? "Clear the selection" : "Select every quest that can run"}
                  />
                  <span className="text-[12px] text-subtle">
                    {selectedLive.size
                      ? selectedLive.size + " selected"
                      : "Select quests to run them one after another"}
                  </span>
                </>
              ) : (
                <span className="text-[12px] text-subtle" />
              )}

              <div className="flex-1" />

              {watching ? (
                <span
                  className="max-w-[320px] truncate-1 text-[12px] text-[#b8bdff]"
                  title={
                    "Discord is crediting this video in the background. You can keep using Discord.\n" +
                    watching.name
                  }
                >
                  Watching the video in the background
                </span>
              ) : queueIds.length > 0 ? (
                <span className="text-[12px] tabular-nums text-[#b8bdff]">
                  {queue?.active
                    ? "Running 1 of " + queueIds.length
                    : queueIds.length + " queued"}
                </span>
              ) : null}

              {watching ? (
                <Button
                  size="sm"
                  variant="ghost"
                  busy={skipWatch.isPending}
                  onClick={() => skipWatch.mutate()}
                  title="Move on without waiting for this video to finish."
                >
                  Skip video
                </Button>
              ) : null}

              {queueIds.length > 0 ? (
                <Button
                  size="sm"
                  variant="ghost"
                  busy={clearQueue.isPending}
                  icon={<TrashIcon size={12} />}
                  onClick={() => clearQueue.mutate()}
                  title="Stop the queue. The quest that is already running keeps running."
                >
                  Clear queue
                </Button>
              ) : null}

              {runnable.length > 0 ? (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={selectedOrdered.length === 0}
                  busy={startQueue.isPending}
                  onClick={() =>
                    startQueue.mutate(selectedOrdered, {
                      onSuccess: (result) => {
                        if (result.ok) setSelected(new Set());
                      },
                    })
                  }
                  title="Run these quests back to back. Unaccepted quests are accepted first; video quests are credited in the background."
                >
                  Start selected
                </Button>
              ) : null}
            </div>
          )}

          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            {visible.length === 0 ? (
              <EmptyState
                title={
                  quests.length
                    ? "Nothing matches these filters"
                    : "No quests offered right now"
                }
                description={
                  quests.length
                    ? "Try another filter, or turn on Show finished to review the completed ones."
                    : "Discord is connected but is not offering you any play or watch quest yet. Check back after the next rotation."
                }
                action={
                  quests.length ? (
                    <Button
                      onClick={() => {
                        setKind("all");
                        setReward("all");
                      }}
                    >
                      Clear filters
                    </Button>
                  ) : null
                }
              />
            ) : (
              visible.map((quest) => (
                <QuestRow
                  key={quest.id}
                  quest={quest}
                  selected={selectedLive.has(quest.id)}
                  selectable={isQueuable(quest)}
                  watching={queue?.watching === quest.id}
                  busy={pendingId === quest.id}
                  onSelect={(next) => toggleSelected(quest.id, next)}
                  onStart={() =>
                    withPending(quest, () =>
                      startQuest.mutate(quest.id, {
                        onSettled: () => setPendingId(null),
                      }),
                    )
                  }
                  onStop={() =>
                    withPending(quest, () =>
                      stopQuest.mutate(quest.id, {
                        onSettled: () => setPendingId(null),
                      }),
                    )
                  }
                  onWatch={() => startQueue.mutate([quest.id])}
                  onClaim={() =>
                    withPending(quest, () =>
                      claimQuest.mutate(quest.id, {
                        onSettled: () => setPendingId(null),
                      }),
                    )
                  }
                />
              ))
            )}
          </div>
        </>
      )}
    </section>
  );
}

/**
 * A toolbar menu button. The popup is anchored to the button, so it opens
 * under the control the user pressed rather than at the pointer.
 */
function MenuButton({
  label,
  value,
  active,
  options,
}: {
  label: string;
  value: string;
  active: boolean;
  options: { label: string; active: boolean; action: () => void }[];
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);

  return (
    <>
      <button
        ref={ref}
        type="button"
        aria-haspopup="menu"
        aria-expanded={anchor !== null}
        onClick={() => {
          const rect = ref.current?.getBoundingClientRect();
          if (!rect) return;
          setAnchor(anchor ? null : { x: rect.left, y: rect.bottom + 4 });
        }}
        className={
          "inline-flex h-6 items-center gap-1 rounded-[4px] px-2 text-[12px] font-medium transition-colors " +
          (active || anchor
            ? "bg-active text-ink"
            : "text-subtle hover:bg-hover hover:text-ink")
        }
        title={label + ": " + value}
      >
        <span className="text-subtle">{label}</span>
        {value}
        <ChevronDownIcon size={11} />
      </button>
      {anchor ? (
        <Menu
          x={anchor.x}
          y={anchor.y}
          onClose={() => setAnchor(null)}
          items={options.map((option) => ({
            label: option.label,
            icon: option.active ? <CheckIcon size={12} /> : <span className="w-3" />,
            action: option.action,
          }))}
        />
      ) : null}
    </>
  );
}
