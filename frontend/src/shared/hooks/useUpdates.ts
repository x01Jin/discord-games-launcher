import { useQuery } from "@tanstack/react-query";
import { bridge } from "../api-client";

const ONE_HOUR = 60 * 60 * 1000;

export function useAppInfo() {
  return useQuery({
    queryKey: ["app-info"],
    queryFn: () => bridge.get_app_info(),
    staleTime: Infinity,
    retry: 0,
  });
}

export function useUpdateStatus() {
  return useQuery({
    queryKey: ["update-status"],
    queryFn: () => bridge.check_for_update(),
    staleTime: ONE_HOUR,
    refetchInterval: ONE_HOUR,
    retry: 0,
  });
}
