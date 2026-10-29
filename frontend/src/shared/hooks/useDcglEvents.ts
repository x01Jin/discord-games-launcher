import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import type { DcglEventDetail } from "../api-client";

function isDcglDetail(value: unknown): value is DcglEventDetail {
  if (typeof value !== "object" || value === null) return false;
  const type = (value as { type?: unknown }).type;
  return type === "library_changed" || type === "quests_changed";
}

/**
 * Backend pushes arrive as a CustomEvent dispatched from Python. Anything that
 * changes library or quest state invalidates the matching caches, so nothing
 * on screen waits for its next poll.
 */
export function useDcglEvents(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const handler = (event: Event) => {
      if (!isDcglDetail((event as CustomEvent).detail)) return;
      for (const key of ["library", "catalogue", "stats", "quests"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
    };
    window.addEventListener("dcgl", handler);
    return () => window.removeEventListener("dcgl", handler);
  }, [queryClient]);
}
