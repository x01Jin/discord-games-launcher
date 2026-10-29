import { useMemo, useState } from "react";
import type { QuestGame } from "../../../shared/api-client";
import { isQueuable } from "../lib/filters";

export function useQuestSelection(runnable: QuestGame[], visible: QuestGame[]) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const selectedLive = useMemo(() => {
    if (selected.size === 0) return selected;
    const live = new Set(runnable.map((quest) => quest.id));
    return new Set([...selected].filter((id) => live.has(id)));
  }, [selected, runnable]);

  const allSelected =
    runnable.length > 0 && runnable.every((quest) => selectedLive.has(quest.id));

  const selectedOrdered = visible
    .filter((quest) => selectedLive.has(quest.id) && isQueuable(quest))
    .map((quest) => quest.id);

  const toggleSelected = (questId: string, next: boolean) => {
    setSelected((current) => {
      const copy = new Set(current);
      if (next) copy.add(questId);
      else copy.delete(questId);
      return copy;
    });
  };

  const toggleAll = () => {
    setSelected(
      allSelected ? new Set() : new Set(runnable.map((quest) => quest.id)),
    );
  };

  return {
    selected,
    selectedLive,
    allSelected,
    selectedOrdered,
    toggleSelected,
    toggleAll,
    setSelected,
  };
}
