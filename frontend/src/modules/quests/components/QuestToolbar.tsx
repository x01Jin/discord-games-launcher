import { useRef, useState } from "react";
import type { SilentModeStatus } from "../../../shared/api-client";
import {
  CheckIcon,
  ChevronDownIcon,
  WrenchIcon,
} from "../../../shared/components/icons";
import { Menu } from "../../../shared/components/Menu";
import { Toolbar } from "../../../shared/components/PageHeader";
import { Button, Switch } from "../../../shared/components/primitives";
import {
  KIND_FILTERS,
  REWARD_FILTERS,
  REWARD_FILTER_LABEL,
  SORTS,
  type KindFilter,
  type RewardFilter,
  type Sort,
} from "../lib/filters";

export function QuestToolbar({
  kind,
  onKind,
  reward,
  onReward,
  sort,
  onSort,
  visibleCount,
  totalCount,
  silent,
  enabling,
  onEnableSilent,
  showFinished,
  onShowFinished,
}: {
  kind: KindFilter;
  onKind: (value: KindFilter) => void;
  reward: RewardFilter;
  onReward: (value: RewardFilter) => void;
  sort: Sort;
  onSort: (value: Sort) => void;
  visibleCount: number;
  totalCount: number;
  silent: SilentModeStatus | undefined;
  enabling: boolean;
  onEnableSilent: () => void;
  showFinished: boolean;
  onShowFinished: (value: boolean) => void;
}) {
  return (
    <Toolbar>
      <div className="flex items-center gap-1" role="group" aria-label="Quest type">
        {KIND_FILTERS.map((entry) => {
          const active = kind === entry.id;
          return (
            <button
              key={entry.id}
              type="button"
              aria-pressed={active}
              onClick={() => onKind(entry.id)}
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
          action: () => onReward(entry.id),
        }))}
      />

      <MenuButton
        label="Sort"
        value={SORTS.find((entry) => entry.id === sort)?.label ?? "Suggested"}
        active={sort !== "suggested"}
        options={SORTS.map((entry) => ({
          label: entry.label,
          active: sort === entry.id,
          action: () => onSort(entry.id),
        }))}
      />

      <span className="text-[12px] text-subtle">
        {visibleCount} shown
        {totalCount > visibleCount ? " of " + totalCount : ""}
      </span>

      <div className="flex-1" />

      {silent && !silent.enabled ? (
        <Button
          size="sm"
          variant="ghost"
          busy={enabling}
          icon={<WrenchIcon size={12} />}
          title="Add the local endpoint to Discord's launch entries."
          onClick={onEnableSilent}
        >
          Set up silent start
        </Button>
      ) : null}

      <Switch
        checked={showFinished}
        onChange={onShowFinished}
        label="Show finished"
      />
    </Toolbar>
  );
}

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
