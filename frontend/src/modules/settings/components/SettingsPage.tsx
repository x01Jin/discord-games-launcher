import { useState } from "react";
import { Dialog } from "../../../shared/components/Dialog";
import { PageHeader } from "../../../shared/components/PageHeader";
import { QuestRunPanel } from "./QuestRunPanel";
import { LauncherRow, Panel, Row } from "./SettingsPrimitives";
import { Button, StatusDot } from "../../../shared/components/primitives";
import {
  RefreshIcon,
  TrashIcon,
  WrenchIcon,
} from "../../../shared/components/icons";
import {
  useDisableSilentMode,
  useEnableSilentMode,
  useQuestStatus,
  useQuests,
  useSetQuestPrefs,
  useSilentMode,
} from "../../../shared/hooks/useQuests";

export function SettingsPage() {
  const silent = useSilentMode();
  const status = useQuestStatus();
  const quests = useQuests();
  const { refetch: refetchQuests, isFetching: questsFetching } = quests;
  const enable = useEnableSilentMode();
  const disable = useDisableSilentMode();
  const setPrefs = useSetQuestPrefs();
  const prefs = quests.data?.prefs;
  const [confirmRemoval, setConfirmRemoval] = useState(false);
  const [tailDraft, setTailDraft] = useState<string | null>(null);

  const commitTail = () => {
    if (tailDraft === null) return;
    const minutes = Math.round(Number(tailDraft));
    setTailDraft(null);
    if (!Number.isFinite(minutes) || prefs?.play_session_tail_min === minutes) return;
    setPrefs.mutate({ play_session_tail_min: Math.min(30, Math.max(0, minutes)) });
  };

  const state = silent.data;
  const launchers = state?.launchers ?? [];
  const patched = state?.patched ?? launchers.filter((item) => item.patched).length;
  const total = state?.total ?? launchers.length;
  const allPatched = total > 0 && patched === total;

  const clientLine =
    status?.installed === false
      ? "Not installed"
      : status
        ? `${status.channel ?? "Discord"} ${status.version ?? ""}`.trim()
        : "Checking…";

  const endpointLine = !status
    ? "Checking…"
    : status.connected
      ? `Port ${status.debug_port}`
      : status.running
        ? "Running without it"
        : "Discord is closed";

  const stateTone = allPatched ? "success" : patched === 0 ? "neutral" : "warning";
  const stateLabel = allPatched
    ? `On for ${patched} of ${total} launch entries`
    : patched === 0
      ? "Off. Discord starts normally."
      : `On for ${patched} of ${total} launch entries`;

  return (
    <section aria-label="Settings" className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Settings"
        subtitle="What the app changes and how to undo it."
        actions={
          <Button
            size="sm"
            variant="ghost"
            busy={questsFetching}
            icon={<RefreshIcon size={13} />}
            onClick={() => {
              void silent.refetch();
              void refetchQuests();
            }}
          >
            Refresh
          </Button>
        }
      />

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[880px] flex-col gap-3 px-5 py-5">
          <Panel
            title="Discord client"
            description="Quests are read from the running client over loopback."
          >
            <Row label="Client">{clientLine}</Row>
            <Row label="Endpoint">{endpointLine}</Row>
          </Panel>

          <QuestRunPanel
            prefs={prefs}
            onPrefs={(values) => setPrefs.mutate(values)}
            tailDraft={tailDraft}
            onTailDraft={setTailDraft}
            onCommitTail={commitTail}
          />

          <Panel
            title="Launch patch"
            description={
              <>
                Adds{" "}
                <code className="font-mono text-[11px] text-muted">
                  --remote-debugging-port={state?.port ?? 9223}
                </code>{" "}
                to every entry Windows starts Discord from. The endpoint is
                loopback only and takes effect on the next start.
              </>
            }
            actions={
              <>
                {patched > 0 ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<TrashIcon size={12} />}
                    onClick={() => setConfirmRemoval(true)}
                    title="Restore every Discord launch entry"
                  >
                    Remove patch
                  </Button>
                ) : null}
                {!allPatched ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<WrenchIcon size={12} />}
                    busy={enable.isPending}
                    onClick={() => enable.mutate()}
                  >
                    Turn on
                  </Button>
                ) : null}
              </>
            }
          >
            <div className="flex items-center gap-2 rounded-[6px] border border-line bg-base/40 px-3 py-2">
              <StatusDot tone={stateTone} />
              <span className="text-[12px] text-muted">{stateLabel}</span>
            </div>

            {state?.error ? (
              <p className="mt-2 text-[12px] leading-[18px] text-[#ff8f8f]">
                {state.error}
              </p>
            ) : null}

            {launchers.length > 0 ? (
              <ul className="mt-2 flex flex-col gap-1.5">
                {launchers.map((launcher) => (
                  <LauncherRow
                    key={launcher.kind + launcher.location}
                    launcher={launcher}
                  />
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[12px] leading-[18px] text-subtle">
                No Discord shortcut, startup entry or Run value was found.
              </p>
            )}

            <p className="mt-2.5 text-[12px] leading-[18px] text-subtle">
              Removing the patch restores the previous command lines. A Discord
              that is already open keeps its endpoint until it closes.
            </p>
          </Panel>
        </div>
      </div>

      <Dialog
        open={confirmRemoval}
        title="Remove the launch patch?"
        danger
        onClose={() => setConfirmRemoval(false)}
        description={
          <>
            {patched === 1
              ? "One launch entry goes back"
              : `${patched} launch entries go back`}{" "}
            to the previous command line. Discord starts normally again, and this
            page can no longer read quests.
            <br />
            A Discord that is already open keeps its endpoint until it closes.
          </>
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmRemoval(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              busy={disable.isPending}
              onClick={() => {
                setConfirmRemoval(false);
                disable.mutate();
              }}
            >
              Remove patch
            </Button>
          </>
        }
      />
    </section>
  );
}
