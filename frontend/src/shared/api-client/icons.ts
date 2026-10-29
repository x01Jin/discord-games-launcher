const DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons";

export function getIconUrl(
  gameId: string,
  iconHash: string,
  size: number = 64,
): string {
  return DISCORD_CDN_URL + "/" + gameId + "/" + iconHash + ".png?size=" + size;
}

export function getQuestAssetUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("https://") || path.startsWith("http://")) return path;
  return "https://cdn.discordapp.com/" + path.replace(/^\/+/, "");
}
