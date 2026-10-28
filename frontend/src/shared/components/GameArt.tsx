import { useState } from "react";
import { getIconUrl, getQuestAssetUrl } from "../api-client";

interface Props {
  name: string;
  gameId?: string | null;
  iconHash?: string | null;
  /** Quest artwork, used before the application icon when present. */
  artPath?: string | null;
  size?: number;
  className?: string;
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 1).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** Stable hue per name, so fallback tiles are not all the same grey. */
function hueFor(name: string): number {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) % 360;
  }
  return hash;
}

/**
 * Square game art. The initials are drawn underneath and the artwork fades in
 * over them, so a slow or blocked CDN request leaves a readable tile instead
 * of an empty box. Sources degrade quest artwork, application icon, initials.
 */
export function GameArt({
  name,
  gameId,
  iconHash,
  artPath,
  size = 40,
  className = "",
}: Props) {
  const questArt = getQuestAssetUrl(artPath ?? null);
  const icon = gameId && iconHash ? getIconUrl(gameId, iconHash, 64) : null;
  const preferred = questArt ?? icon;
  // Tracked by URL rather than a boolean: a changed source gets its own chance
  // to load, without an effect that resets state after the fact.
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const [loadedSrc, setLoadedSrc] = useState<string | null>(null);

  const showImage = preferred !== null && failedSrc !== preferred;
  const hue = hueFor(name);

  return (
    <div
      style={{ width: size, height: size }}
      className={
        "relative shrink-0 overflow-hidden rounded-[6px] bg-white/[0.06] " + className
      }
    >
      <span
        aria-hidden="true"
        style={{
          fontSize: Math.max(10, Math.round(size * 0.34)),
          backgroundColor: "hsla(" + hue + ", 38%, 44%, 0.3)",
          color: "hsl(" + hue + ", 58%, 78%)",
        }}
        className="absolute inset-0 flex items-center justify-center font-semibold"
      >
        {initials(name)}
      </span>
      {showImage ? (
        <img
          src={preferred}
          alt=""
          loading="lazy"
          decoding="async"
          draggable={false}
          onLoad={() => setLoadedSrc(preferred)}
          onError={() => setFailedSrc(preferred)}
          style={{ opacity: loadedSrc === preferred ? 1 : 0 }}
          className="absolute inset-0 size-full object-cover transition-opacity duration-150"
        />
      ) : null}
    </div>
  );
}
