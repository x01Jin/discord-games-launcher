import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import type { CatalogueGame, ListGamesResult } from "../../../shared/api-client";
import { useUiStore } from "../../../shared/store/ui-store";
import { catalogueService, PAGE_SIZE } from "../services/catalogue-service";

interface CataloguePage {
  games: CatalogueGame[];
  total: number;
  error?: string;
}

export function useCatalogueGames(query: string) {
  const trimmed = query.trim();
  return useInfiniteQuery<
    CataloguePage,
    Error,
    InfiniteData<CataloguePage>,
    readonly unknown[],
    number
  >({
    queryKey: ["catalogue", trimmed] as const,
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      if (trimmed) {
        const result = await catalogueService.search(trimmed);
        return { games: result.games, total: result.games.length, error: result.error };
      }
      const result: ListGamesResult = await catalogueService.list(pageParam);
      return { games: result.games, total: result.total, error: result.error };
    },
    getNextPageParam: (lastPage, allPages) => {
      if (trimmed) return undefined;
      const loaded = allPages.reduce((count, page) => count + page.games.length, 0);
      if (lastPage.error) return undefined;
      if (lastPage.games.length === 0) return undefined;
      return loaded < lastPage.total ? loaded : undefined;
    },
    staleTime: 30_000,
  });
}

export function flattenedGames(
  data: InfiniteData<CataloguePage> | undefined,
): CatalogueGame[] {
  if (!data) return [];
  return data.pages.flatMap((page) => page.games);
}

export { PAGE_SIZE };

export function useAddGames() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const clearSelected = useUiStore((state) => state.clearSelected);

  return useMutation({
    mutationFn: (ids: string[]) =>
      ids.length === 1
        ? catalogueService.addOne(ids[0]).then((result) => ({
            added: result.ok ? 1 : 0,
            failed: result.ok ? 0 : 1,
            message: result.message,
          }))
        : catalogueService.addMany(ids),
    onSuccess: (result) => {
      clearSelected();
      void queryClient.invalidateQueries({ queryKey: ["catalogue"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      pushToast(result.message, result.failed ? "error" : "success");
    },
    onError: () => pushToast("Could not add games. Check the backend.", "error"),
  });
}
