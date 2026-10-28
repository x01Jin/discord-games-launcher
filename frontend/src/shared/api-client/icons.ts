const DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons";

/** Direct CDN URL for a game icon (the webview HTTP cache handles repeats). */
export function getIconUrl(
  gameId: string,
  iconHash: string,
  size: number = 64,
): string {
  return DISCORD_CDN_URL + "/" + gameId + "/" + iconHash + ".png?size=" + size;
}

/**
 * Quest art paths come back relative to the media CDN root, e.g.
 * "quests/<quest>/<asset>.png". Placeholders are filtered out by the backend.
 */
export function getQuestAssetUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("https://") || path.startsWith("http://")) return path;
  return "https://cdn.discordapp.com/" + path.replace(/^\/+/, "");
}
