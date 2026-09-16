import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useUiStore } from "../../../shared/store/ui-store";
import { libraryService } from "../services/library-service";

function invalidate(qc: ReturnType<typeof useQueryClient>): void {
  void qc.invalidateQueries({ queryKey: ["library"] });
  void qc.invalidateQueries({ queryKey: ["running"] });
  void qc.invalidateQueries({ queryKey: ["stats"] });
  void qc.invalidateQueries({ queryKey: ["catalogue"] });
}

export function useLibraryGames() {
  return useQuery({
    queryKey: ["library"],
    queryFn: () => libraryService.getLibrary(),
  });
}

export function useToggleGame() {
  const qc = useQueryClient();
  const pushToast = useUiStore((s) => s.pushToast);
  return useMutation({
    mutationFn: ({ id, running }: { id: string; running: boolean }) =>
      running ? libraryService.stop(id) : libraryService.start(id),
    onSuccess: (r) => {
      invalidate(qc);
      pushToast(r.message, r.ok ? "success" : "error");
    },
    onError: () =>
      pushToast(
        "Could not change game state. Check the backend connection and try again.",
        "error",
      ),
  });
}

export function useStopAll() {
  const qc = useQueryClient();
  const pushToast = useUiStore((s) => s.pushToast);
  return useMutation({
    mutationFn: () => libraryService.stopAll(),
    onSuccess: (r) => {
      invalidate(qc);
      pushToast(`Stopped ${r.stopped} game(s).`, "success");
    },
    onError: () =>
      pushToast(
        "Could not stop games. Check the backend connection and try again.",
        "error",
      ),
  });
}

export function useRepairLibrary() {
  const qc = useQueryClient();
  const pushToast = useUiStore((s) => s.pushToast);
  return useMutation({
    mutationFn: () => libraryService.repair(),
    onSuccess: (r) => {
      invalidate(qc);
      pushToast(r.message, r.ok ? "success" : "error");
    },
    onError: () =>
      pushToast(
        "Could not repair the library. Check the backend connection and try again.",
        "error",
      ),
  });
}

export function useRemoveGame() {
  const qc = useQueryClient();
  const pushToast = useUiStore((s) => s.pushToast);
  return useMutation({
    mutationFn: (id: string) => libraryService.remove(id),
    onSuccess: (r) => {
      invalidate(qc);
      pushToast(r.message, r.ok ? "success" : "error");
    },
    onError: () =>
      pushToast(
        "Could not remove the game. Check the backend connection and try again.",
        "error",
      ),
  });
}
