import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bridge } from "../api-client";
import type {
  DiscordStatus,
  QuestPrefs,
  QuestsResult,
  SilentModeStatus,
} from "../api-client";
import { useUiStore } from "../store/ui-store";

/**
 * The quest list, read from the running Discord client. One key, so the
 * sidebar, the page, and every mutation share one fetch.
 */
export function useQuests() {
  return useQuery({
    queryKey: ["quests"],
    queryFn: () => bridge.get_quests(),
    // While the client is missing or unreachable, look again often: Discord
    // may be starting, or the user may have just opened it. Once quests are
    // flowing, the client's own refresh cadence is the limit, so back off.
    refetchInterval: (query) => {
      const data = query.state.data as QuestsResult | undefined;
      return data?.connected ? 20_000 : 4_000;
    },
    staleTime: 3_000,
    retry: 0,
  });
}

/** Just the connection state, for chrome that stays mounted on every page. */
export function useQuestStatus(): DiscordStatus | undefined {
  const { data } = useQuests();
  return (data as QuestsResult | undefined)?.status;
}

function useQuestMutation(
  mutationFn: (questId: string) => Promise<{ ok: boolean; message: string }>,
) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn,
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
      void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      pushToast(result.message, result.ok ? "success" : "error");
    },
    onError: () =>
      pushToast("The backend did not answer. Try again.", "error"),
  });
}

export function useStartQuest() {
  return useQuestMutation((questId) => bridge.start_quest(questId));
}

export function useStopQuest() {
  return useQuestMutation((questId) => bridge.stop_quest(questId));
}

/** Start several accepted play quests one after another. */
export function useStartQuestQueue() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (questIds: string[]) => bridge.start_quest_queue(questIds),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      pushToast(result.message, result.ok ? "success" : "error");
    },
    onError: () => pushToast("The backend did not answer. Try again.", "error"),
  });
}

export function useClearQuestQueue() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: () => bridge.clear_quest_queue(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      pushToast(
        result.cleared
          ? "Cleared " + result.cleared + " queued quest(s)."
          : "The queue was already empty.",
        "success",
      );
    },
    onError: () => pushToast("The backend did not answer. Try again.", "error"),
  });
}

/** Stop waiting on the video the queue opened in Discord. */
export function useSkipQuestWatch() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: () => bridge.skip_quest_watch(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      pushToast(result.message, result.ok ? "success" : "error");
    },
    onError: () => pushToast("The backend did not answer. Try again.", "error"),
  });
}

/** Put the pending queue in a new order, as shown on the Running page. */
export function useReorderQuestQueue() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (questIds: string[]) => bridge.reorder_quest_queue(questIds),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      if (!result.ok) pushToast(result.message, "error");
    },
    onError: () => pushToast("The backend did not answer. Try again.", "error"),
  });
}

/** Drop one quest from the pending queue. */
export function useRemoveFromQuestQueue() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (questId: string) => bridge.remove_from_quest_queue(questId),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      pushToast(result.message, result.ok ? "success" : "error");
    },
    onError: () => pushToast("The backend did not answer. Try again.", "error"),
  });
}

/** The pause between quests. Stored next to the database. */
export function useSetQuestPrefs() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (values: Partial<QuestPrefs>) => bridge.set_quest_prefs(values),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      if (!result.ok) pushToast(result.message ?? "Could not save that.", "error");
    },
    onError: () => pushToast("Could not save that setting.", "error"),
  });
}

/**
 * Enable quest reading. Restarts Discord only when it is already open without
 * the endpoint; a closed client is started with it instead.
 */
export function useConnectDiscord() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: () => bridge.connect_discord(),
    onSuccess: (result) => {
      pushToast(result.message, result.ok ? "success" : "error");
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
    },
    onError: () =>
      pushToast("Could not reach the backend to connect Discord.", "error"),
  });
}

/** Start Discord with quest reading enabled, without touching a running one. */
export function useStartDiscord() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: () => bridge.start_discord(),
    onSuccess: (result) => {
      pushToast(result.message, result.ok ? "success" : "error");
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
    },
    onError: () => pushToast("Could not start Discord.", "error"),
  });
}

/**
 * Bring Discord's quest page forward. Used for quests this app cannot finish
 * itself: watching a video, and accepting a play quest before it pays out.
 */
export function useOpenInDiscord() {
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (questId: string) => bridge.open_quest_in_discord(questId),
    onSuccess: (result) => {
      if (!result.ok) pushToast(result.message, "error");
    },
    onError: () => pushToast("Could not open Discord.", "error"),
  });
}
/**
 * Which Windows launch entries carry the debug endpoint.
 *
 * This changes rarely (only when the user turns it on or off, or when a Discord
 * update rewrites the Run value), so it is cached for a minute and refreshed
 * when the connect panel mounts.
 */
export function useSilentMode() {
  return useQuery({
    queryKey: ["silent-mode"],
    queryFn: () => bridge.silent_mode_status() as Promise<SilentModeStatus>,
    staleTime: 60_000,
    retry: 0,
  });
}

export function useEnableSilentMode() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: () => bridge.enable_silent_mode(),
    onSuccess: (result) => {
      pushToast(
        result.message ??
          (result.ok ? "Silent connection is on." : "Could not turn silent connection on."),
        result.ok ? "success" : "error",
      );
      void queryClient.invalidateQueries({ queryKey: ["silent-mode"] });
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
    },
    onError: () => pushToast("Could not reach the backend.", "error"),
  });
}

export function useDisableSilentMode() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: () => bridge.disable_silent_mode(),
    onSuccess: (result) => {
      pushToast(
        result.message ??
          (result.ok ? "Silent connection is off." : "Could not turn silent connection off."),
        result.ok ? "success" : "error",
      );
      void queryClient.invalidateQueries({ queryKey: ["silent-mode"] });
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
    },
    onError: () => pushToast("Could not reach the backend.", "error"),
  });
}
