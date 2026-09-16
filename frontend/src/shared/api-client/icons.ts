const DISCORD_CDN_URL = "https://cdn.discordapp.com/app-icons";

/** Direct CDN URL for a game icon (no local caching by design). */
export function getIconUrl(
  gameId: string,
  iconHash: string,
  size: number = 64,
): string {
  return `${DISCORD_CDN_URL}/${gameId}/${iconHash}.png?size=${size}`;
}
