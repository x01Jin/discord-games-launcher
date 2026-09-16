import { useQuery } from "@tanstack/react-query";
import { bridge } from "../api-client";

function format(n: number): string {
  return n.toLocaleString("en-US");
}

/** Live stats bar, refreshed every 5 seconds. In-flow footer fill. */
export function Footer() {
  const { data } = useQuery({
    queryKey: ["stats"],
    queryFn: () => bridge.get_stats(),
    refetchInterval: 5000,
  });

  return (
    <footer className="z-30 flex shrink-0 flex-wrap items-center justify-center gap-x-2 gap-y-1 border-t border-white/5 bg-ink px-4 py-3 text-center text-xs uppercase tracking-wide text-muted">
      <span className="whitespace-nowrap">
        Cache: {data ? format(data.cached_games) : "—"}
      </span>
      <span aria-hidden="true">|</span>
      <span className="whitespace-nowrap">
        No Win: {data ? format(data.games_no_win_exes) : "—"}
      </span>
      <span aria-hidden="true">|</span>
      <span className="whitespace-nowrap">
        Library: {data ? format(data.library_games) : "—"}
      </span>
      <span aria-hidden="true">|</span>
      <span className="whitespace-nowrap">
        Running: {data ? format(data.running_processes) : "—"}
      </span>
    </footer>
  );
}
