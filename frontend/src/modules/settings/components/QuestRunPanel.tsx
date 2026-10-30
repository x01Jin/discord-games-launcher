import type { QuestPrefs } from "../../../shared/api-client";
import { Switch } from "../../../shared/components/primitives";
import { Panel } from "./SettingsPrimitives";

export function QuestRunPanel({
  prefs,
  onPrefs,
  tailDraft,
  onTailDraft,
  onCommitTail,
}: {
  prefs: QuestPrefs | undefined;
  onPrefs: (values: Partial<QuestPrefs>) => void;
  tailDraft: string | null;
  onTailDraft: (value: string) => void;
  onCommitTail: () => void;
}) {
  return (
    <Panel
      title="Quest runs"
      description="Choose whether a running quest shows the game on your Discord profile or stays private."
    >
      <div className="flex items-center justify-between gap-4 border-t border-line/70 py-2 first:border-t-0">
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-muted">Play activity</p>
          <p className="mt-0.5 text-[12px] leading-[18px] text-subtle">
            Show activity puts the game on your Discord profile while the quest
            runs. Private runs earn the same time and show nothing. Neither
            launches a game.
          </p>
        </div>
        <div
          role="group"
          aria-label="Play activity"
          className="flex shrink-0 overflow-hidden rounded-[4px] border border-line-strong"
        >
          {(
            [
              ["activity", "Show activity"],
              ["silent", "Private"],
            ] as const
          ).map(([mode, label]) => {
            const active = (prefs?.run_mode ?? "activity") === mode;
            return (
              <button
                key={mode}
                type="button"
                aria-pressed={active}
                onClick={() => {
                  if (!active) onPrefs({ run_mode: mode });
                }}
                className={
                  "h-7 px-2.5 text-[12px] transition-colors " +
                  (active
                    ? "bg-active text-ink"
                    : "text-muted hover:bg-hover hover:text-ink")
                }
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-line/70 py-2">
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-muted">Pause between quests</p>
          <p className="mt-0.5 text-[12px] leading-[18px] text-subtle">
            The next queued quest starts after a random wait of 10 seconds to
            this many minutes. 0 starts it immediately.
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-1.5">
          <input
            type="number"
            min={0}
            max={30}
            value={tailDraft ?? String(prefs?.play_session_tail_min ?? 2)}
            onChange={(event) => onTailDraft(event.target.value)}
            onBlur={onCommitTail}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
            className="h-7 w-14 rounded-[4px] border border-line-strong bg-base px-2 text-right text-[12px] tabular-nums text-ink outline-none focus:border-accent"
            aria-label="Pause between quests in minutes"
          />
          <span className="text-[12px] text-subtle">min</span>
        </label>
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-line/70 py-2">
        <div className="min-w-0 flex-1">
          <p className="text-[12px] text-muted">Test mode</p>
          <p className="mt-0.5 text-[12px] leading-[18px] text-subtle">
            Runs a quest only far enough to prove enrolment, crediting and
            progress work, then stops it. Nothing is claimed and the quest stays
            unfinished, so it can be run again. Video quests stop after three
            progress posts, game quests after two credited beats.
          </p>
        </div>
        <Switch
          checked={prefs?.test_mode ?? false}
          onChange={(next) => onPrefs({ test_mode: next })}
          label="Test mode"
          hideLabel
        />
      </div>
    </Panel>
  );
}
