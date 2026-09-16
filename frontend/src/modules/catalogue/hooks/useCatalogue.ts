import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useUiStore } from "../../../shared/store/ui-store";
import { catalogueService } from "../services/catalogue-service";

export function useCatalogueGames(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ["catalogue", q],
    queryFn: async () => {
      if (q) {
        const r = await catalogueService.search(q);
        return { games: r.games, total: r.games.length };
      }
      return catalogueService.list(0);
    },
    placeholderData: keepPreviousData,
  });
}

export function useAddGames() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((s) => s.pushToast);
  const clearSelected = useUiStore((s) => s.clearSelected);

  return useMutation({
    mutationFn: (ids: string[]) =>
      ids.length === 1
        ? catalogueService.addOne(ids[0]).then((r) => ({
            added: r.ok ? 1 : 0,
            failed: r.ok ? 0 : 1,
            message: r.message,
          }))
        : catalogueService.addMany(ids),
    onSuccess: (r) => {
      clearSelected();
      void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      pushToast(r.message, r.failed ? "error" : "success");
    },
    onError: () =>
      pushToast(
        "Could not add games. Check the backend connection and try again.",
        "error",
      ),
  });
}
