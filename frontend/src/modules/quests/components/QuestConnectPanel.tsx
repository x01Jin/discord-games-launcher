import type { DiscordStatus, SilentModeStatus } from "../../../shared/api-client";
import {
  AlertIcon,
  CheckIcon,
  DiscordIcon,
  PlayIcon,
  RefreshIcon,
} from "../../../shared/components/icons";
import { Button, StatusDot } from "../../../shared/components/primitives";

interface Props {
  status: DiscordStatus | undefined;
  silent: SilentModeStatus | undefined;
  error: string | null;
  connecting: boolean;
  starting: boolean;
  disabling: boolean;
  canStart: boolean;
  onConnect: () => void;
  onStartDiscord: () => void;
  onRefresh: () => void;
  onDisableSilent: () => void;
}

function Step({ index, title, children }: { index: number; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-active text-[11px] font-semibold text-muted">
        {index}
      </span>
      <span className="min-w-0 flex-1 text-[12px] leading-5 text-subtle">
        <span className="font-medium text-muted">{title}</span>
        {children}
      </span>
    </li>
  );
}

export function QuestConnectPanel({
  status,
  silent,
  error,
  connecting,
  starting,
  disabling,
  canStart,
  onConnect,
  onStartDiscord,
  onRefresh,
  onDisableSilent,
}: Props) {
  const notInstalled = status?.installed === false;
  const notRunning = Boolean(status?.installed && !status.running);
  const noEndpoint = Boolean(status?.running && !status.connected);
  const setupDone = Boolean(silent?.enabled ?? status?.silent);

  const title = notInstalled
    ? "Discord is not installed"
    : notRunning
      ? "Discord is not running"
      : setupDone
        ? "One restart finishes setup"
        : noEndpoint
          ? "Connect to the Discord client"
          : "Quests unavailable";

  return (
    <div className="mx-auto flex w-full max-w-[560px] flex-col gap-4 px-6 py-8">
      <div className="flex items-center gap-2.5">
        <DiscordIcon size={20} className="text-[#5865f2]" />
        <h2 className="text-[16px] font-semibold text-ink">{title}</h2>
      </div>

      <p className="text-[13px] leading-[21px] text-muted">
        {notInstalled ? (
          <>
            Quests are read from the Discord desktop client. Install it, sign
            in, then return here.
          </>
        ) : notRunning ? (
          <>
            Discord is closed. Start it here and this page can read quests when
            it loads.
          </>
        ) : setupDone ? (
          <>
            The switch is in place. Discord is still running the copy started
            before it, so it needs one more start.
          </>
        ) : (
          <>
            Discord is running without the local debug endpoint. One switch adds
            it for future starts.
          </>
        )}
      </p>

      {noEndpoint && !setupDone ? (
        <ol className="flex flex-col gap-3 rounded-[6px] border border-line bg-raised/60 px-4 py-3.5">
          <Step index={1} title="Set up silent start.">
            {" "}
            Adds the switch to Discord's shortcuts and startup entry.
          </Step>
          <Step index={2} title="Discord restarts once.">
            {" "}
            You stay signed in. Calls and games in Discord end.
          </Step>
          <Step index={3} title="Nothing to repeat.">
            {" "}
            The list appears whenever Discord starts.
          </Step>
        </ol>
      ) : null}

      {setupDone && noEndpoint ? (
        <p className="flex items-start gap-2 rounded-[6px] border border-line bg-raised px-3 py-2.5 text-[12px] leading-5 text-muted">
          <span className="pt-0.5 text-success">
            <CheckIcon size={14} />
          </span>
          <span>
            Silent connection is on for {silent ? (silent.patched ?? 0) : 0} of{" "}
            {silent ? (silent.total ?? 0) : 0} launch entries. Close Discord
            from the tray and open it again, or press the button below.
          </span>
        </p>
      ) : null}

      {error && !noEndpoint ? (
        <div className="flex items-start gap-2 rounded-[6px] border border-line-strong bg-raised px-3 py-2.5 text-[12px] leading-5 text-muted">
          <span className="pt-0.5 text-warning">
            <AlertIcon size={14} />
          </span>
          <span className="min-w-0 flex-1 break-words">{error}</span>
        </div>
      ) : null}

      {status ? (
        <dl className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-1.5 rounded-[6px] border border-line bg-raised/60 px-3 py-2.5 text-[12px]">
          <dt className="text-subtle">Client</dt>
          <dd className="flex items-center gap-2 text-muted">
            <StatusDot tone={status.running ? "success" : "neutral"} />
            {status.running ? "Running" : "Stopped"}
            {status.version ? (
              <span className="text-subtle">
                {status.channel} {status.version}
              </span>
            ) : null}
          </dd>
          <dt className="text-subtle">Endpoint</dt>
          <dd
            className="text-muted"
            title={status.connected ? (status.url ?? undefined) : (status.error ?? undefined)}
          >
            {status.connected ? "open on port " + status.debug_port : "closed"}
          </dd>
          <dt className="text-subtle">Silent connection</dt>
          <dd className="flex items-center gap-2 text-muted">
            <StatusDot tone={setupDone ? "success" : "neutral"} />
            {setupDone ? "on" : "off"}
            {silent && (silent.total ?? 0) > 0 ? (
              <span className="text-subtle">
                {silent.patched ?? 0} of {silent.total ?? 0} launch entries
              </span>
            ) : null}
          </dd>
        </dl>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {canStart ? (
          <Button
            variant="primary"
            busy={starting}
            icon={<PlayIcon size={11} />}
            onClick={onStartDiscord}
          >
            Start Discord
          </Button>
        ) : null}
        {noEndpoint ? (
          <Button variant="primary" busy={connecting} onClick={onConnect}>
            {setupDone ? "Restart Discord now" : "Set up and restart Discord"}
          </Button>
        ) : null}
        <Button
          variant={canStart || noEndpoint ? "secondary" : "primary"}
          icon={<RefreshIcon size={13} />}
          onClick={onRefresh}
        >
          Check again
        </Button>
        {setupDone ? (
          <Button
            variant="ghost"
            busy={disabling}
            className="ml-auto"
            onClick={onDisableSilent}
            title="Remove the launch switch from every Discord shortcut and startup entry"
          >
            Turn silent connection off
          </Button>
        ) : null}
      </div>
    </div>
  );
}
