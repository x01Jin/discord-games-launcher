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

export interface RemoveManyResult {
  removed: number;
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

export type QuestState = "ready" | "running" | "completed" | "expired" | "unresolved";

export type QuestKind = "play" | "watch" | "watch_mobile";

export type QuestAction =
  | "run"
  | "stop"
  | "open"
  | "mobile"
  | "done"
  | "claim"
  | "unsupported";

export interface QuestReward {
  label: string | null;

  labels: string[];
  orbs: number | null;
  premium_orbs: number | null;

  avatar_decoration: boolean;

  in_game: boolean;
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
  state: QuestState;

  claimed: boolean;

  claimable: boolean;

  queued: boolean;
}

export interface ClaimResult extends MutResult {
  needs_user_action?: boolean;
}

export interface QuestPrefs {

  play_session_tail_min: number;

  run_mode: "activity" | "silent";
}

export interface QuestQueue {
  ids: string[];
  active: string | null;

  watching: string | null;
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

  silent?: boolean;

  silent_wanted?: boolean;
  silent_port?: number;
}

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

  orbs?: number | null;
  prefs?: QuestPrefs;
  queue?: QuestQueue;
}

export interface QuestPrefsResult {
  ok: boolean;
  prefs: QuestPrefs;
  message?: string;
}

export interface ClearQueueResult {
  ok: boolean;
  cleared: number;
}

export type DcglEventDetail =
  | { type: "library_changed" }
  | { type: "quests_changed" };

export interface AppInfo {
  version: string;
  repo_url: string;
  release_url: string;
}

export interface UpdateStatus extends AppInfo {
  latest: string | null;
  update_available: boolean;
  error: string | null;
}

export interface PywebviewApi {
  get_app_info(): Promise<AppInfo>;
  check_for_update(force?: boolean): Promise<UpdateStatus>;
  open_project_page(target?: "repo" | "latest"): Promise<MutResult>;

  list_games(limit: number, offset: number): Promise<ListGamesResult>;
  search_games(query: string, limit: number): Promise<SearchGamesResult>;
  add_to_library(game_id: string): Promise<MutResult>;
  add_many(game_ids: string[]): Promise<AddManyResult>;
  get_library(): Promise<LibraryResult>;
  start_game(game_id: string): Promise<MutResult>;
  stop_game(game_id: string): Promise<MutResult>;
  stop_all_games(): Promise<StopAllResult>;
  remove_from_library(game_id: string): Promise<MutResult>;
  remove_many(game_ids: string[]): Promise<RemoveManyResult>;
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
  accept_quest(quest_id: string): Promise<MutResult>;
  claim_quest_reward(quest_id: string): Promise<ClaimResult>;
  stop_quest(quest_id: string): Promise<MutResult>;
  start_quest_queue(quest_ids: string[]): Promise<MutResult>;
  clear_quest_queue(): Promise<ClearQueueResult>;
  skip_quest_watch(): Promise<MutResult>;
  reorder_quest_queue(quest_ids: string[]): Promise<MutResult>;
  remove_from_quest_queue(quest_id: string): Promise<MutResult>;
  get_quest_prefs(): Promise<QuestPrefsResult>;
  set_quest_prefs(values: Partial<QuestPrefs>): Promise<QuestPrefsResult>;

  silent_mode_status(): Promise<SilentModeStatus>;
  enable_silent_mode(): Promise<SilentModeResult>;
  disable_silent_mode(): Promise<SilentModeResult>;
}

declare global {
  interface Window {
    pywebview?: { api: PywebviewApi };
  }
}
