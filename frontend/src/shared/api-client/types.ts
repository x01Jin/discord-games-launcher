export interface CatalogueGame {
  id: string;
  name: string;
  icon_hash: string | null;
  win_exes: string[];
  in_library: boolean;
}

export interface LibraryGame {
  game_id: string;
  name: string;
  icon_hash: string | null;
  process_name: string;
  is_running: boolean;
}

export interface ListGamesResult {
  games: CatalogueGame[];
  total: number;
  error?: string;
}

export interface SearchGamesResult {
  games: CatalogueGame[];
  error?: string;
}

export interface MutResult {
  ok: boolean;
  message: string;
}

export interface AddManyResult {
  added: number;
  failed: number;
  message: string;
}

export interface LibraryResult {
  games: LibraryGame[];
  error?: string;
}

export interface StatsResult {
  cached_games: number;
  library_games: number;
  running_processes: number;
  games_no_win_exes: number;
}

export interface RunningResult {
  running: string[];
}

export interface SyncResult {
  synced: boolean;
  count: number;
  skipped: number;
  message: string;
}

export interface StopAllResult {
  stopped: number;
}

export interface RepairResult {
  ok: boolean;
  message: string;
  summary: Record<string, number>;
}

export type DcglEventDetail = { type: "library_changed" };

export interface PywebviewApi {
  list_games(limit: number, offset: number): Promise<ListGamesResult>;
  search_games(query: string, limit: number): Promise<SearchGamesResult>;
  add_to_library(game_id: string): Promise<MutResult>;
  add_many(game_ids: string[]): Promise<AddManyResult>;
  get_library(): Promise<LibraryResult>;
  start_game(game_id: string): Promise<MutResult>;
  stop_game(game_id: string): Promise<MutResult>;
  stop_all_games(): Promise<StopAllResult>;
  remove_from_library(game_id: string): Promise<MutResult>;
  repair_library(): Promise<RepairResult>;
  sync_catalogue(): Promise<SyncResult>;
  get_stats(): Promise<StatsResult>;
  get_running(): Promise<RunningResult>;
}

declare global {
  interface Window {
    pywebview?: { api: PywebviewApi };
  }
}
