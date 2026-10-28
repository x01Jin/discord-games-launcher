import type { ReactNode } from "react";
import logoUrl from "../../assets/dcgl.png";
import { useQuestStatus } from "../hooks/useQuests";
import { useStats } from "../hooks/useStats";
import { formatCount } from "../lib/format";
import { useUiStore, type Page } from "../store/ui-store";
import {
  CatalogueIcon,
  DiscordIcon,
  LibraryIcon,
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

/** Left rail: identity, three destinations, and live backend state. */
export function Sidebar() {
  const page = useUiStore((state) => state.page);
  const setPage = useUiStore((state) => state.setPage);
  const stats = useStats();

  const entries: NavEntry[] = [
    { id: "quests", label: "Quests", icon: <QuestsIcon size={16} />, hint: "Offers from the running client" },
    {
      id: "catalogue",
      label: "Catalogue",
      icon: <CatalogueIcon size={16} />,
      count: stats.data
        ? stats.data.cached_games - stats.data.games_no_win_exes
        : undefined,
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

      <div className="shrink-0 border-t border-line px-3 py-2.5">
        <div className="flex items-center gap-2 text-[12px] text-subtle">
          <DiscordIcon size={14} />
          <span className="flex-1 truncate">Discord client</span>
          {stats.data && stats.data.running_processes > 0 ? (
            <span className="tabular-nums text-muted">
              {stats.data.running_processes} fake
            </span>
          ) : null}
        </div>
        <ClientState />
      </div>
    </aside>
  );
}

/** One line of live client state, shared with the quests query. */
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
