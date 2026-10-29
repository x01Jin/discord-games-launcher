

export function formatCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US");
}

export function formatDuration(seconds: number | null | undefined): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "—";
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return total + "s";
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return minutes + "m";
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours < 24) return restMinutes ? hours + "h " + restMinutes + "m" : hours + "h";
  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? days + "d " + restHours + "h" : days + "d";
}

export function formatTimeLeft(seconds: number | null | undefined): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "No end date";
  if (seconds <= 0) return "Expired";
  if (seconds < 3600) return Math.max(1, Math.round(seconds / 60)) + "m left";
  return formatDuration(seconds) + " left";
}

export function formatProgress(elapsed: number, target: number): string {
  if (!target) return "—";
  return formatDuration(elapsed) + " of " + formatDuration(target);
}

export function formatPercent(ratio: number): string {
  if (!Number.isFinite(ratio)) return "0%";
  return Math.round(Math.max(0, Math.min(1, ratio)) * 100) + "%";
}
