import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import type { DcglEventDetail } from "../api-client";

function isDcglDetail(v: unknown): v is DcglEventDetail {
  if (typeof v !== "object" || v === null) return false;
  return (v as { type?: unknown }).type === "library_changed";
}

/**
 * Subscribes to backend async events pushed via
 * `window.dispatchEvent(new CustomEvent('dcgl', {detail}))`
 * and invalidates the matching React Query caches.
 */
export function useDcglEvents(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!isDcglDetail(detail)) return;
      void queryClient.invalidateQueries({ queryKey: ["library"] });
      void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      void queryClient.invalidateQueries({ queryKey: ["running"] });
    };
    window.addEventListener("dcgl", handler);
    return () => window.removeEventListener("dcgl", handler);
  }, [queryClient]);
}
