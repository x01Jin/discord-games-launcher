import { bridge } from "../../../shared/api-client";

export const libraryService = {
  getLibrary() {
    return bridge.get_library();
  },
  start(gameId: string) {
    return bridge.start_game(gameId);
  },
  stop(gameId: string) {
    return bridge.stop_game(gameId);
  },
  stopAll() {
    return bridge.stop_all_games();
  },
  remove(gameId: string) {
    return bridge.remove_from_library(gameId);
  },
  repair() {
    return bridge.repair_library();
  },
  getRunning() {
    return bridge.get_running();
  },
};
