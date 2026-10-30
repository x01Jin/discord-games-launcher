import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bridge } from "../api-client";
import type {
  DiscordStatus,
  QuestPrefs,
  QuestsResult,
  SilentModeStatus,
} from "../api-client";
import { useUiStore } from "../store/ui-store";

export function useQuests() {
  return useQuery({
    queryKey: ["quests"],
    queryFn: () => bridge.get_quests(),
    refetchInterval: (query) => {
      const data = query.state.data as QuestsResult | undefined;
      if (!data?.connected) return 4_000;
      return (data.quests?.length ?? 0) > 0 ? 60_000 : 5_000;
    },
    staleTime: 3_000,
    retry: 0,
  });
}

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

export function useClaimQuest() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (questId: string) => bridge.claim_quest_reward(questId),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["quests"] });
      if (result.ok) {
        pushToast(result.message, "success");
      } else if (result.needs_user_action) {
        pushToast(result.message, "info");
        window.setTimeout(() => {
          void queryClient.invalidateQueries({ queryKey: ["quests"] });
        }, 2500);
      } else {
        pushToast(result.message, "error");
      }
    },
    onError: () => pushToast("Could not claim the reward.", "error"),
  });
}

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

export function useSilentMode() {
  return useQuery({
    queryKey: ["silent-mode"],
    queryFn: () => bridge.silent_mode_status() as Promise<SilentModeStatus>,
    refetchInterval: 10_000,
    staleTime: 5_000,
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
