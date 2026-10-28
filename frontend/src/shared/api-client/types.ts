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

/* --------------------------------------------------------------------------
 * Quests, read from the running Discord client
 * ----------------------------------------------------------------------- */

export type QuestState = "ready" | "running" | "completed" | "expired" | "unresolved";

/** Which task the client is offering. Only "play" can be finished here. */
export type QuestKind = "play" | "watch" | "watch_mobile";

/** What the row's button should do. */
export type QuestAction =
  | "run"
  | "stop"
  | "enroll"
  | "open"
  | "mobile"
  | "done"
  | "unsupported";

export interface QuestReward {
  label: string | null;
  orbs: number | null;
  premium_orbs: number | null;
}

export interface QuestGame {
  id: string;
  name: string;
  game_name: string;
  publisher: string | null;
  application_id: string | null;
  kind: QuestKind;
  task_key: string | null;
  action: QuestAction;
  enrolled: boolean;
  icon_hash: string | null;
  tile_url: string | null;
  hero_url: string | null;
  logotype_url: string | null;
  video_url: string | null;
  video_thumbnail: string | null;
  accent: string | null;
  expires_at: string | null;
  seconds_left: number | null;
  target_seconds: number;
  progress_seconds: number;
  progress: number;
  task_keys: string[];
  reward: QuestReward;
  executables: string[];
  process_name: string | null;
  in_library: boolean;
  is_running: boolean;
  shares_game_with: number;
  state: QuestState;
}

export interface DiscordStatus {
  installed: boolean;
  running: boolean;
  connected: boolean;
  channel?: string | null;
  version?: string | null;
  exe_path?: string | null;
  debug_port?: number | null;
  title?: string | null;
  url?: string | null;
  error?: string | null;
  hint: string;
  cached?: boolean;
  /** Every Windows launch entry now carries the debug endpoint. */
  silent?: boolean;
  /** The user asked for silent connection and it should be kept that way. */
  silent_wanted?: boolean;
  silent_port?: number;
}

/** One place Windows starts Discord from. */
export interface SilentLauncher {
  kind: string;
  location: string;
  target: string;
  arguments: string;
  patched: boolean;
}

export interface SilentModeStatus {
  port: number;
  enabled: boolean;
  wanted: boolean;
  patched?: number;
  total?: number;
  launchers: SilentLauncher[];
  error?: string;
}

export interface SilentModeResult {
  ok: boolean;
  message?: string;
  updated?: string[];
  restored?: string[];
  failed?: string[];
}

export interface QuestsResult {
  connected: boolean;
  quests: QuestGame[];
  status?: DiscordStatus;
  error: string | null;
  fetched_at: number | null;
  account?: { id: string; username: string | null } | null;
  suspended_until?: string | null;
  enrollment_blocked_until?: string | null;
  total_quests?: number;
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

  discord_status(): Promise<DiscordStatus>;
  get_quests(force?: boolean): Promise<QuestsResult>;
  connect_discord(): Promise<MutResult>;
  start_discord(): Promise<MutResult>;
  open_quest_in_discord(quest_id: string): Promise<MutResult>;
  start_quest(quest_id: string): Promise<MutResult>;
  stop_quest(quest_id: string): Promise<MutResult>;

  silent_mode_status(): Promise<SilentModeStatus>;
  enable_silent_mode(): Promise<SilentModeResult>;
  disable_silent_mode(): Promise<SilentModeResult>;
}

declare global {
  interface Window {
    pywebview?: { api: PywebviewApi };
  }
}
