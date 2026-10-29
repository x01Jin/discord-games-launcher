import { useState, type ReactNode } from "react";
import type { SilentLauncher } from "../../../shared/api-client";
import { Dialog } from "../../../shared/components/Dialog";
import { PageHeader } from "../../../shared/components/PageHeader";
import {
  Button,
  Chip,
  StatusDot,
  Switch,
} from "../../../shared/components/primitives";
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

function Panel({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-[8px] border border-line bg-raised/50">
      <div className="flex items-start justify-between gap-4 px-4 pt-3.5">
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
          {description ? (
            <p className="mt-1 text-[12px] leading-[18px] text-subtle">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2 pt-0.5">{actions}</div>
        ) : null}
      </div>
      {children ? <div className="px-4 pb-3.5 pt-2">{children}</div> : null}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-line/70 py-2 first:border-t-0">
      <span className="shrink-0 text-[12px] text-subtle">{label}</span>
      <span className="min-w-0 truncate text-right text-[12px] text-muted">
        {children}
      </span>
    </div>
  );
}

function LauncherRow({ launcher }: { launcher: SilentLauncher }) {
  return (
    <li className="rounded-[6px] border border-line bg-base/40 px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-medium text-ink">{launcher.kind}</span>
        <Chip tone={launcher.patched ? "success" : "neutral"}>
          {launcher.patched ? "Patched" : "Original"}
        </Chip>
      </div>
      <p className="mt-1 truncate text-[11px] text-subtle" title={launcher.location}>
        {launcher.location}
      </p>
      <code className="mt-1 block whitespace-pre-wrap break-words font-mono text-[11px] leading-4 text-subtle">
        {launcher.arguments}
      </code>
    </li>
  );
}

/** Settings: what the app changes on this machine, and how to undo it. */
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
        subtitle="What this app changes on this machine, and how to undo it."
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
            description="Quests are read from the running client over a loopback endpoint, so the request stays on this machine."
          >
            <Row label="Client">{clientLine}</Row>
            <Row label="Endpoint">{endpointLine}</Row>
          </Panel>

          <Panel
            title="Quest runs"
            description="How a dummy game behaves while it earns quest time. Both settings are saved on this machine and apply to the next run."
          >
            <div className="flex items-center justify-between gap-4 border-t border-line/70 py-2 first:border-t-0">
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-muted">Hide activity</p>
                <p className="mt-0.5 text-[12px] leading-[18px] text-subtle">
                  Turn off Discord's own "Playing" status while a quest runs.
                  Your previous setting comes back when the run ends.
                </p>
              </div>
              <Switch
                checked={prefs?.hide_activity ?? false}
                onChange={(next) => setPrefs.mutate({ hide_activity: next })}
                label="Hide the Playing status during runs"
                hideLabel
              />
            </div>

            <div className="flex items-center justify-between gap-4 border-t border-line/70 py-2">
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-muted">Play session tail</p>
                <p className="mt-0.5 text-[12px] leading-[18px] text-subtle">
                  Keep the game running for a random slice of these minutes
                  after the target is reached, so a session does not stop on the
                  exact second. 0 stops immediately.
                </p>
              </div>
              <label className="flex shrink-0 items-center gap-1.5">
                <input
                  type="number"
                  min={0}
                  max={30}
                  value={tailDraft ?? String(prefs?.play_session_tail_min ?? 2)}
                  onChange={(event) => setTailDraft(event.target.value)}
                  onBlur={commitTail}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur();
                  }}
                  className="h-7 w-14 rounded-[4px] border border-line-strong bg-base px-2 text-right text-[12px] tabular-nums text-ink outline-none focus:border-accent"
                  aria-label="Play session tail in minutes"
                />
                <span className="text-[12px] text-subtle">min</span>
              </label>
            </div>
          </Panel>

          <Panel
            title="Launch patch"
            description={
              <>
                Adds{" "}
                <code className="font-mono text-[11px] text-muted">
                  --remote-debugging-port={state?.port ?? 9223}
                </code>{" "}
                to every entry Windows starts Discord from. The endpoint only
                exists on loopback, and the switch takes effect the next time
                Discord starts.
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
                    title="Restore the original command line of every Discord launch entry"
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
                No Discord shortcut, startup entry or Run value was found, so
                there is nothing to patch.
              </p>
            )}

            <p className="mt-2.5 text-[12px] leading-[18px] text-subtle">
              Removing the patch restores the exact command lines these entries
              had before. A Discord that is already open keeps the endpoint it
              started with until it is closed.
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
            to the command line it had before. Discord starts normally again, and
            this page can no longer read quests.
            <br />
            A Discord that is already open keeps the endpoint until it is closed.
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
