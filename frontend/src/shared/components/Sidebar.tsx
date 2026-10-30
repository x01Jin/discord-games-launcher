import type { ReactNode } from "react";
import logoUrl from "../../assets/dcgl.png";
import { bridge } from "../api-client";
import { useQuests, useQuestStatus } from "../hooks/useQuests";
import { useAppInfo, useUpdateStatus } from "../hooks/useUpdates";
import { useStats } from "../hooks/useStats";
import { formatCount } from "../lib/format";
import { useUiStore, type Page } from "../store/ui-store";
import {
  CatalogueIcon,
  DiscordIcon,
  GithubIcon,
  LibraryIcon,
  PlayIcon,
  QuestsIcon,
  SettingsIcon,
} from "./icons";
import { StatusDot } from "./primitives";

interface NavEntry {
  id: Page;
  label: string;
  icon: ReactNode;
  count?: number;
  hint?: string;
}

export function Sidebar() {
  const page = useUiStore((state) => state.page);
  const setPage = useUiStore((state) => state.setPage);
  const stats = useStats();
  const { data: questsData } = useQuests();
  const runningIds = new Set(
    (questsData?.quests ?? [])
      .filter((quest) => quest.state === "running")
      .map((quest) => quest.id),
  );
  const activeQuests =
    runningIds.size +
    (questsData?.queue?.ids ?? []).filter((id) => !runningIds.has(id)).length;

  const entries: NavEntry[] = [
    { id: "quests", label: "Quests", icon: <QuestsIcon size={16} />, hint: "Quests offered by Discord" },
    {
      id: "running",
      label: "Running",
      icon: <PlayIcon size={16} />,
      count: activeQuests || undefined,
      hint: "Quests and games in progress",
    },
    {
      id: "catalogue",
      label: "Catalogue",
      icon: <CatalogueIcon size={16} />,
      hint: "Games Discord can detect",
    },
    {
      id: "library",
      label: "Library",
      icon: <LibraryIcon size={16} />,
      count: stats.data?.library_games,
      hint: "Games you added",
    },
  ];

  const renderEntry = (entry: NavEntry) => {
    const active = entry.id === page;
    return (
      <button
        key={entry.id}
        type="button"
        title={entry.hint}
        aria-current={active ? "page" : undefined}
        onClick={() => setPage(entry.id)}
        className={[
          "mb-0.5 flex h-[34px] w-full items-center gap-2.5 rounded-[4px] px-2 text-[14px]",
          "transition-colors duration-100",
          active ? "bg-active text-ink" : "text-muted hover:bg-hover hover:text-ink",
        ].join(" ")}
      >
        <span className={active ? "text-ink" : "text-subtle"}>{entry.icon}</span>
        <span className="flex-1 truncate text-left font-medium">{entry.label}</span>
        {typeof entry.count === "number" ? (
          <span className="shrink-0 rounded-[3px] bg-black/25 px-1.5 text-[11px] font-medium tabular-nums text-subtle">
            {formatCount(entry.count)}
          </span>
        ) : null}
      </button>
    );
  };

  return (
    <aside className="flex h-full w-[228px] shrink-0 flex-col border-r border-line bg-base">
      <div className="flex h-14 shrink-0 items-center gap-2.5 px-3.5">
        <img src={logoUrl} alt="" className="size-8 shrink-0 rounded-[7px]" />
        <p className="min-w-0 truncate text-[13px] font-semibold text-ink">
          Discord Games Launcher
        </p>
      </div>

      <nav aria-label="Sections" className="flex-1 overflow-y-auto px-2 pt-1">
        {entries.map(renderEntry)}
      </nav>

      <div className="shrink-0 px-2 pb-1">
        {renderEntry({
          id: "settings",
          label: "Settings",
          icon: <SettingsIcon size={16} />,
          hint: "Discord connection and the launch patch",
        })}
      </div>

      <div className="shrink-0 px-3 py-2">
        <ProjectLink />
      </div>

      <div className="shrink-0 border-t border-line px-3 py-2.5">
        <div className="flex items-center gap-2 text-[12px] text-subtle">
          <DiscordIcon size={14} />
          <span className="flex-1 truncate">Discord client</span>
          {stats.data && stats.data.running_processes > 0 ? (
            <span
              className="tabular-nums text-muted"
              title="Dummy processes running for quests"
            >
              {stats.data.running_processes} running
            </span>
          ) : null}
        </div>
        <ClientState />
      </div>
    </aside>
  );
}

function ProjectLink() {
  const { data: info } = useAppInfo();
  const { data: update } = useUpdateStatus();
  const version = info?.version ?? "";
  const available = Boolean(update?.update_available);
  const target = available ? "latest" : "repo";
  const title = available
    ? "Version " + (update?.latest ?? "") + " is available"
    : "Open the GitHub repository";

  return (
    <button
      type="button"
      onClick={() => void bridge.open_project_page(target)}
      title={title}
      className="flex w-full items-center gap-2 text-left text-[12px] text-subtle transition-colors hover:text-ink"
    >
      <GithubIcon size={14} />
      <span className="flex-1 truncate">{version ? "v" + version : "GitHub"}</span>
      {available ? (
        <span className="shrink-0 rounded-[3px] bg-warning/15 px-1.5 py-0.5 text-[11px] font-semibold text-warning">
          Update available
        </span>
      ) : null}
    </button>
  );
}

function ClientState() {
  const status = useQuestStatus();
  const tone = status?.connected
    ? "success"
    : status?.running
      ? "warning"
      : "neutral";
  const label = status?.connected
    ? "Connected" + (status.debug_port ? " · " + status.debug_port : "")
    : status?.running
      ? "Running, no endpoint"
      : status?.installed === false
        ? "Not installed"
        : "Not running";

  return (
    <div className="mt-1 flex items-center gap-2 text-[12px] text-subtle">
      <StatusDot tone={tone} />
      <span className="truncate" title={status?.hint}>
        {label}
      </span>
    </div>
  );
}
