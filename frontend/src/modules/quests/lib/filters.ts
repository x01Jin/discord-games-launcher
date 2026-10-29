import type { QuestGame, QuestReward } from "../../../shared/api-client";

export type KindFilter = "all" | "play" | "watch";
export type RewardFilter = "all" | "orbs" | "decoration" | "in_game";
export type Sort = "suggested" | "expiring" | "orbs" | "progress";

export const KIND_FILTERS: { id: KindFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "play", label: "Play" },
  { id: "watch", label: "Watch" },
];

export const REWARD_FILTERS: { id: RewardFilter; label: string }[] = [
  { id: "all", label: "All rewards" },
  { id: "orbs", label: "Orbs" },
  { id: "decoration", label: "Avatar decoration" },
  { id: "in_game", label: "In-game item" },
];

export const SORTS: { id: Sort; label: string }[] = [
  { id: "suggested", label: "Suggested" },
  { id: "expiring", label: "Expiring soon" },
  { id: "orbs", label: "Most orbs" },
  { id: "progress", label: "Most progress" },
];

export const REWARD_FILTER_LABEL: Record<RewardFilter, string> = {
  all: "All rewards",
  orbs: "Orbs",
  decoration: "Avatar decoration",
  in_game: "In-game item",
};

export const NO_QUESTS: QuestGame[] = [];

export function isQueuable(quest: QuestGame) {
  if (quest.queued) return false;
  if (quest.kind === "play") return quest.action === "run";
  if (quest.kind === "watch" || quest.kind === "watch_mobile") {
    return quest.action === "open";
  }
  return false;
}

export function matchesReward(reward: QuestReward, filter: RewardFilter) {
  if (filter === "orbs") return typeof reward.orbs === "number";
  if (filter === "decoration") return reward.avatar_decoration;
  if (filter === "in_game") return reward.in_game;
  return true;
}

export function sortQuests(quests: QuestGame[], sort: Sort) {
  if (sort === "suggested") return quests;
  const copy = [...quests];
  if (sort === "expiring") {
    copy.sort((a, b) => {
      const left = a.seconds_left ?? Number.MAX_SAFE_INTEGER;
      const right = b.seconds_left ?? Number.MAX_SAFE_INTEGER;
      return left - right;
    });
  } else if (sort === "orbs") {
    copy.sort((a, b) => (b.reward.orbs ?? -1) - (a.reward.orbs ?? -1));
  } else {
    copy.sort((a, b) => b.progress - a.progress);
  }
  return copy;
}
