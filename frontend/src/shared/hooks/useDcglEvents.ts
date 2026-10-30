import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import type { DcglEventDetail, QuestsResult } from "../api-client";

function isDcglDetail(value: unknown): value is DcglEventDetail {
  if (typeof value !== "object" || value === null) return false;
  const type = (value as { type?: unknown }).type;
  return (
    type === "library_changed" ||
    type === "quests_changed" ||
    type === "quest_progress"
  );
}

export function useDcglEvents(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (!isDcglDetail(detail)) return;

      if (detail.type === "quest_progress") {
        applyProgress(queryClient, detail);
        return;
      }

      for (const key of ["library", "catalogue", "stats", "quests"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
    };
    window.addEventListener("dcgl", handler);
    return () => window.removeEventListener("dcgl", handler);
  }, [queryClient]);
}

function applyProgress(
  queryClient: ReturnType<typeof useQueryClient>,
  detail: Extract<DcglEventDetail, { type: "quest_progress" }>,
): void {
  queryClient.setQueryData<QuestsResult>(["quests"], (current) => {
    if (!current) return current;
    const credited = Math.max(0, Math.round(detail.credited));
    let changed = false;
    const quests = current.quests.map((quest) => {
      if (quest.id !== detail.quest_id) return quest;
      if (credited <= quest.progress_seconds) return quest;
      const target = quest.target_seconds || detail.target || 0;
      changed = true;
      return {
        ...quest,
        progress_seconds: credited,
        progress: target > 0 ? Math.min(1, credited / target) : quest.progress,
      };
    });
    return changed ? { ...current, quests } : current;
  });
}
