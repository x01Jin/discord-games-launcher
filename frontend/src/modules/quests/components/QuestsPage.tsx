import { useMemo, useState } from "react";
import type { QuestGame } from "../../../shared/api-client";
import { RefreshIcon, WrenchIcon } from "../../../shared/components/icons";
import { PageHeader, Toolbar } from "../../../shared/components/PageHeader";
import { Button, EmptyState, Skeleton, Switch } from "../../../shared/components/primitives";
import {
  useConnectDiscord,
  useDisableSilentMode,
  useEnableSilentMode,
  useOpenInDiscord,
  useQuests,
  useSilentMode,
  useStartDiscord,
  useStartQuest,
  useStopQuest,
} from "../../../shared/hooks/useQuests";
import { useUiStore } from "../../../shared/store/ui-store";
import { QuestConnectPanel } from "./QuestConnectPanel";
import { QuestRow } from "./QuestRow";

type Filter = "all" | "play" | "watch";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "play", label: "Play" },
  { id: "watch", label: "Watch" },
];

/** Stable empty list so the memos below do not re-run on every render. */
const NO_QUESTS: QuestGame[] = [];

export function QuestsPage() {
  const { data, isLoading, isFetching, isError, refetch } = useQuests();
  const connect = useConnectDiscord();
  const startDiscord = useStartDiscord();
  const openInDiscord = useOpenInDiscord();
  const { data: silent } = useSilentMode();
  const enableSilent = useEnableSilentMode();
  const disableSilent = useDisableSilentMode();
  const startQuest = useStartQuest();
  const stopQuest = useStopQuest();
  const showFinished = useUiStore((state) => state.showFinished);
  const setShowFinished = useUiStore((state) => state.setShowFinished);
  const [filter, setFilter] = useState<Filter>("all");
  const [pendingId, setPendingId] = useState<string | null>(null);

  const quests = data?.quests ?? NO_QUESTS;

  const counts = useMemo(() => {
    const tally = { open: 0, running: 0, finished: 0 };
    for (const quest of quests) {
      if (quest.state === "running") tally.running += 1;
      if (quest.action === "done") tally.finished += 1;
      else tally.open += 1;
    }
    return tally;
  }, [quests]);

  const visible = useMemo(() => {
    return quests.filter((quest) => {
      const done = quest.action === "done";
      if (!showFinished && done) return false;
      if (filter === "play") return quest.kind === "play";
      if (filter === "watch") return quest.kind !== "play";
      return true;
    });
  }, [quests, showFinished, filter]);

  const connected = Boolean(data?.connected);

  const subtitle = connected
    ? [
        counts.open + " open",
        counts.running ? counts.running + " running" : null,
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
          <Button
            size="sm"
            variant="ghost"
            busy={isFetching && !isLoading}
            icon={<RefreshIcon size={13} />}
            onClick={() => void refetch()}
          >
            Refresh
          </Button>
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
              {FILTERS.map((entry) => {
                const active = filter === entry.id;
                return (
                  <button
                    key={entry.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setFilter(entry.id)}
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

          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            {visible.length === 0 ? (
              <EmptyState
                title={
                  quests.length
                    ? "Nothing matches this filter"
                    : "No quests offered right now"
                }
                description={
                  quests.length
                    ? "Try another filter, or turn on Show finished to review the completed ones."
                    : "Discord is connected but is not offering you any play or watch quest yet. Check back after the next rotation."
                }
                action={
                  quests.length ? (
                    <Button onClick={() => setFilter("all")}>Show all</Button>
                  ) : null
                }
              />
            ) : (
              visible.map((quest) => (
                <QuestRow
                  key={quest.id}
                  quest={quest}
                  busy={pendingId === quest.id}
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
                  onOpen={() => openInDiscord.mutate(quest.id)}
                />
              ))
            )}
          </div>
        </>
      )}
    </section>
  );
}
