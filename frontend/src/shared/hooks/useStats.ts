import { useQuery } from "@tanstack/react-query";
import { bridge } from "../api-client";

/** Backend counts. Invalidated by the bridge event, polled as a backstop. */
export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => bridge.get_stats(),
    refetchInterval: 20_000,
    staleTime: 5_000,
  });
}
