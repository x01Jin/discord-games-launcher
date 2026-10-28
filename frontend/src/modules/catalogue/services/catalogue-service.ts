import { bridge } from "../../../shared/api-client";

export const PAGE_SIZE = 200;

export const catalogueService = {
  list(offset = 0) {
    return bridge.list_games(PAGE_SIZE, offset);
  },
  search(query: string) {
    return bridge.search_games(query, PAGE_SIZE);
  },
  addOne(gameId: string) {
    return bridge.add_to_library(gameId);
  },
  addMany(gameIds: string[]) {
    return bridge.add_many(gameIds);
  },
};
