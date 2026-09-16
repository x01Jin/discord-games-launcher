import { useState } from "react";
import { getIconUrl } from "../api-client";

interface Props {
  gameId: string;
  iconHash: string | null;
  name: string;
}

/** Discord CDN game icon with an initial-letter fallback. */
export function GameIcon({ gameId, iconHash, name }: Props) {
  const [failed, setFailed] = useState(false);

  if (!iconHash || failed) {
    return (
      <span
        aria-hidden="true"
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-peri/20 text-sm font-bold text-peri"
      >
        {(name.trim().charAt(0) || "?").toUpperCase()}
      </span>
    );
  }

  return (
    <img
      src={getIconUrl(gameId, iconHash)}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-10 w-10 shrink-0 rounded-md object-cover"
    />
  );
}
