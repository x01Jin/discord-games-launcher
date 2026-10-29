import { useMemo, useState } from "react";
import type { QuestGame } from "../../../shared/api-client";
import {
  OrbIcon,
  RefreshIcon,
  TrashIcon,
} from "../../../shared/components/icons";
import { PageHeader } from "../../../shared/components/PageHeader";
import {
  Button,
  Checkbox,
  EmptyState,
  Skeleton,
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
import { NO_QUESTS, isQueuable, matchesReward, sortQuests } from "../lib/filters";
import type { KindFilter, RewardFilter, Sort } from "../lib/filters";
import { useQuestSelection } from "../hooks/useQuestSelection";
import { QuestConnectPanel } from "./QuestConnectPanel";
import { QuestRow } from "./QuestRow";
import { QuestToolbar } from "./QuestToolbar";

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

  const {
    selectedLive,
    allSelected,
    selectedOrdered,
    toggleSelected,
    toggleAll,
    setSelected,
  } = useQuestSelection(runnable, visible);

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
          <QuestToolbar
            kind={kind}
            onKind={setKind}
            reward={reward}
            onReward={setReward}
            sort={sort}
            onSort={setSort}
            visibleCount={visible.length}
            totalCount={quests.length}
            silent={silent}
            enabling={enableSilent.isPending}
            onEnableSilent={() => enableSilent.mutate()}
            showFinished={showFinished}
            onShowFinished={setShowFinished}
          />

          {(runnable.length > 0 || queueIds.length > 0) && (
            <div className="flex items-center gap-3 border-b border-line bg-base/40 px-5 py-1.5">
              {runnable.length > 0 ? (
                <>
                  <Checkbox
                    checked={allSelected}
                    onChange={toggleAll}
                    label={allSelected ? "Clear the selection" : "Select every quest that can run"}
                  />
                  <span className="text-[12px] text-subtle">
                    {selectedLive.size
                      ? selectedLive.size + " selected"
                      : "Select quests to run in order"}
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
                    "Discord is crediting this video. You can keep using Discord.\n" +
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
                  title="Stop the queue. A running quest keeps running."
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
                  title="Run the selected quests in order."
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
                    ? "Try another filter or turn on Show finished."
                    : "Discord is not offering any play or watch quests right now."
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
