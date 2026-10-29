import { useQuery } from "@tanstack/react-query";
import { bridge } from "../api-client";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => bridge.get_stats(),
    refetchInterval: 20_000,
    staleTime: 5_000,
  });
}
