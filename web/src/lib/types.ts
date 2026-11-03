export type Tier = "S" | "A" | "B" | "SKIP";

export type ContestStatus =
  | "NEW"
  | "RECOMMENDED"
  | "INTERESTED"
  | "ENTERING"
  | "SUBMITTED"
  | "IGNORE"
  | "EXPIRED";

export interface Score {
  total: number;
  tier: Tier;
  evaluator: string;
  parts: Record<string, number>;
  reasons: string[];
  risks: string[];
  estimated_workdays: string | null;
  idea_seeds: string[];
  updated_at: string | null;
}

export interface Contest {
  key: string;
  source: string;
  source_id: string;
  title: string;
  organizer: string | null;
  organizer_type: string | null;
  url: string;
  homepage: string | null;
  categories: string[];
  eligibility: string[];
  keywords: string[];
  start_date: string | null;
  deadline: string | null;
  days_left: number | null;
  prize_text: string | null;
  top_prize_krw: number | null;
  total_prize_krw: number | null;
  best_prize_krw: number | null;
  status: ContestStatus;
  first_seen: string;
  last_seen: string;
  is_new_today: boolean;
  tags: string[];
  /** 같은 공모전이 여러 소스에 올라온 경우의 묶음 크기. */
  duplicate_count: number;
  duplicate_sources: string[];
  score: Score | null;
}

export interface ContestDetail extends Contest {
  benefits: string[];
  detail_text: string | null;
  project: Project | null;
  history: { from_status: string | null; to_status: string; created_at: string }[];
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface MatrixPoint {
  key: string;
  title: string;
  organizer: string | null;
  tier: Tier;
  total: number;
  win: number;
  value: number;
  prize: number | null;
  days_left: number | null;
}

export interface ScoutState {
  phase: "idle" | "running" | "done" | "failed";
  run_id: number | null;
  started_at: string | null;
  finished_at: string | null;
  trigger: string;
  sources: Record<string, "pending" | "scanning" | "done" | "failed">;
  source_stats: Record<string, SourceStats>;
  new_contests: { title: string; tier: Tier; total: number; source: string }[];
  status: string | null;
  message: string | null;
  errors: { source: string; reason: string }[];
}

export interface SourceStats {
  source: string;
  robots: string;
  list_pages: number;
  discovered: number;
  new: number;
  existing: number;
  details_fetched: number;
  requests: number;
  errors: number;
  skipped_reason: string | null;
}

export interface ScheduleStatus {
  thread_alive: boolean;
  enabled: boolean;
  time: string;
  last_triggered: string | null;
  next_run: string | null;
}

export interface Dashboard {
  kpi: {
    new_today: number;
    s_tier: number;
    ending_soon: number;
    active_contests: number;
  };
  top_opportunities: Contest[];
  matrix: MatrixPoint[];
  new_contests: Contest[];
  last_run: {
    id: number;
    started_at: string;
    finished_at: string | null;
    status: string;
    total_new: number;
  } | null;
  has_any_data: boolean;
  scout: ScoutState;
  schedule: ScheduleStatus;
}

export interface Facets {
  tags: { tag: string; count: number }[];
  sources: { source: string; count: number }[];
  statuses: Record<string, number>;
  tiers: Record<string, number>;
}

export interface ScoutRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: "RUNNING" | "SUCCESS" | "PARTIAL" | "FAILED";
  trigger: string;
  sources: string[];
  total_new: number;
  total_seen: number;
  requests: number;
  duration_sec: number | null;
  stats: Record<string, SourceStats>;
  errors: { source: string; reason: string }[];
  new_titles: { key: string; title: string; tier: Tier; total: number }[];
}

export interface SourceOverview {
  name: string;
  entry_url: string;
  needs_detail_request: boolean;
  stored_contests: number;
  last_checked: string | null;
  last_status: string | null;
  robots: string | null;
  last_discovered: number | null;
  last_new: number | null;
  skipped_reason: string | null;
  errors: number;
}

export interface Analytics {
  discovery: {
    this_week: number;
    last_week: number;
    delta_pct: number | null;
    daily: { date: string; count: number }[];
  };
  categories: { name: string; count: number }[];
  tiers: { name: string; count: number }[];
  recommended_vs_ignored: { recommended: number; ignored: number };
  prize_distribution: { name: string; count: number }[];
  deadline_distribution: { name: string; count: number }[];
  sources: { name: string; count: number }[];
  selection: {
    s_tier_shortlist_rate: number | null;
    s_tier_total: number;
    video_selection_rate: number | null;
    video_total: number;
    avg_selected_prize: number | null;
    selected_count: number;
  };
}

export interface Project {
  id: number;
  contest_key: string;
  title: string;
  brief: string | null;
  deadline: string | null;
  requirements: string | null;
  stage: string;
  stage_index: number;
  stage_count: number;
  progress: number;
  next_action: string | null;
  created_at: string;
  updated_at: string;
  days_left: number | null;
}

export interface Settings {
  crawl: {
    delay: number;
    timeout: number;
    pages: number;
    limit: number | null;
    respect_robots: boolean;
    user_agent: string | null;
  };
  schedule: { enabled: boolean; time: string };
  enabled_sources: string[];
  available_sources: { name: string; entry_url: string }[];
  profile: {
    weights: Record<string, number>;
    strong_keywords: string[];
    preferred_keywords: string[];
    negative_keywords: string[];
    tier_thresholds: Record<string, number>;
    min_days_left: number;
    strong_prize_krw: number;
    good_prize_krw: number;
  };
  part_labels: Record<string, string>;
  scheduler: ScheduleStatus;
  paths: Record<string, string>;
  capabilities: Record<string, boolean>;
  rescored?: number;
}
