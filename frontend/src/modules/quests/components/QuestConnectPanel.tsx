import type { DiscordStatus, SilentModeStatus } from "../../../shared/api-client";
import {
  AlertIcon,
  DiscordIcon,
  PlayIcon,
  RefreshIcon,
  TrashIcon,
} from "../../../shared/components/icons";
import { Button, StatusDot } from "../../../shared/components/primitives";

interface Props {
  status: DiscordStatus | undefined;
  silent: SilentModeStatus | undefined;
  error: string | null;
  connecting: boolean;
  starting: boolean;
  disabling: boolean;
  onConnect: () => void;
  onStartDiscord: () => void;
  onRefresh: () => void;
  onDisableSilent: () => void;
}

export function QuestConnectPanel({
  status,
  silent,
  error,
  connecting,
  starting,
  disabling,
  onConnect,
  onStartDiscord,
  onRefresh,
  onDisableSilent,
}: Props) {
  const notInstalled = status?.installed === false;
  const running = Boolean(status?.running);
  const patched = Boolean(silent?.enabled ?? status?.silent);

  const title = notInstalled
    ? "Discord is not installed"
    : !running
      ? "Discord is not running"
      : patched
        ? "One restart finishes setup"
        : "Discord is running without the endpoint";

  const body = notInstalled ? (
    <>Quests are read from the Discord desktop client. Install it, sign in, then return here.</>
  ) : !running ? (
    patched ? (
      <>
        The launch patch is in place. Start Discord and this page can read quests.
      </>
    ) : (
      <>
        Quests need a local endpoint that has to exist when Discord starts.
        Patching the launch entries and starting Discord here does both in one
        step.
      </>
    )
  ) : patched ? (
    <>
      The launch patch is in place. Discord is still running the copy started
      before it, so it needs one more start.
    </>
  ) : (
    <>
      Discord is open without the local endpoint. Patching the launch entries
      and restarting Discord once turns it on. You stay signed in.
    </>
  );

  const primary = running
    ? {
        label: patched ? "Restart Discord now" : "Patch and restart Discord",
        onClick: onConnect,
        busy: connecting,
      }
    : {
        label: patched ? "Start Discord" : "Patch and run Discord",
        onClick: onStartDiscord,
        busy: starting,
      };

  return (
    <div className="mx-auto flex w-full max-w-[560px] flex-col gap-4 px-6 py-8">
      <div className="flex items-center gap-2.5">
        <DiscordIcon size={20} className="text-[#5865f2]" />
        <h2 className="text-[16px] font-semibold text-ink">{title}</h2>
      </div>

      <p className="text-[13px] leading-[21px] text-muted">{body}</p>

      {error && !notInstalled ? (
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
            <StatusDot tone={running ? "success" : "neutral"} />
            {running ? "Running" : "Stopped"}
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
          <dt className="text-subtle">Launch patch</dt>
          <dd className="flex items-center gap-2 text-muted">
            <StatusDot tone={patched ? "success" : "neutral"} />
            {patched ? "on" : "off"}
            {silent && (silent.total ?? 0) > 0 ? (
              <span className="text-subtle">
                {silent.patched ?? 0} of {silent.total ?? 0} launch entries
              </span>
            ) : null}
          </dd>
        </dl>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {notInstalled ? null : (
          <Button
            variant="primary"
            busy={primary.busy}
            icon={<PlayIcon size={11} />}
            onClick={primary.onClick}
            title={
              patched
                ? "Discord is already patched, so this only starts it"
                : "Adds the endpoint to every launch entry, then starts Discord with it"
            }
          >
            {primary.label}
          </Button>
        )}
        <Button
          variant={notInstalled ? "primary" : "secondary"}
          icon={<RefreshIcon size={13} />}
          onClick={onRefresh}
        >
          Check again
        </Button>
        {patched ? (
          <Button
            variant="ghost"
            busy={disabling}
            className="ml-auto"
            onClick={onDisableSilent}
            icon={<TrashIcon size={12} />}
            title={
              running
                ? "Removes the endpoint from every launch entry and restarts Discord without it"
                : "Removes the endpoint from every launch entry"
            }
          >
            Remove launch patch
          </Button>
        ) : null}
      </div>
    </div>
  );
}
