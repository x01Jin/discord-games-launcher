import { bridge } from "../../../shared/api-client";

const PAGE_LIMIT = 200;

export const catalogueService = {
  list(offset = 0) {
    return bridge.list_games(PAGE_LIMIT, offset);
  },
  search(query: string) {
    return bridge.search_games(query, PAGE_LIMIT);
  },
  addOne(gameId: string) {
    return bridge.add_to_library(gameId);
  },
  addMany(gameIds: string[]) {
    return bridge.add_many(gameIds);
  },
};
