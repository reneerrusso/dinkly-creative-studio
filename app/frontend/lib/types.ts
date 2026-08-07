export type Confidence = "high" | "medium" | "low";

export type DinklyAgentVisualState = "idle" | "learning" | "preparing" | "generating" | "reviewing" | "repairing" | "waiting_for_human" | "success" | "error";

export interface AgentTask {
  id: string;
  source_channel: "web" | "slack" | "scheduled" | "learning";
  source_thread_id: string;
  user_instruction: string;
  task_type: string;
  status: "queued" | "running" | "cancellation_requested" | "waiting_for_human" | "completed" | "failed" | "cancelled";
  priority: number;
  context: Record<string, unknown>;
  run_ids: string[];
  artifact_ids: string[];
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentConversationMessage {
  id: string;
  channel: "web" | "slack";
  thread_id: string;
  message: string;
  role: "user" | "agent" | "system";
  created_at: string;
  linked_task_ids: string[];
  linked_run_ids: string[];
  linked_artifact_ids: string[];
}

export interface AgentWorkHistory {
  id: string;
  kind: string;
  status: string;
  message: string;
  timestamp: string;
  run_ids: string[];
  artifact_ids: string[];
  source_channel: string;
  task_instruction?: string;
  stopped_at?: string | null;
  duration_seconds?: number | null;
  completed_artifact_count?: number;
}

export interface AgentWorkspace {
  agent: DinklyAgentRuntimeState;
  waiting: { concepts: number; comics: number; brain_updates: number };
  recent_work: AgentWorkHistory[];
  brain_updates: DinklyAgentLearning[];
  queued_tasks: number;
  running_tasks: number;
  current_task?: AgentTask | null;
  current_run?: GenerationRun | null;
}

export interface AgentApprovals {
  concepts: Array<Record<string, unknown>>;
  comics: GenerationRun[];
  brain_updates: DinklyAgentLearning[];
}

export interface DinklyAgentRuntimeState {
  state: DinklyAgentVisualState;
  status: string;
  status_kind: "Idle" | "Active" | "Waiting" | "Warning";
  message: string;
  last_event: string;
  last_event_at: string;
  source_run_id: string | null;
  source_event_id: string | null;
  details: Record<string, unknown>;
  expires_at: string | null;
  updated_at: string;
  expression: { state: string; custom: boolean; path: string; fallback_path: string };
}

export interface DinklyAgentActivity {
  id: string;
  state: DinklyAgentVisualState;
  message: string;
  source_run_id: string | null;
  source_event_id: string | null;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface DinklyAgentLearning {
  id: string;
  learning_type: string;
  statement: string;
  evidence_ids: string[];
  confidence: Confidence;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DashboardData {
  metrics: Record<string, number>;
  continue_working: Record<string, unknown[]>;
  strongest_learnings: Learning[];
  performance: PatternData;
  welcome: boolean;
  workflows: { name: string; description: string }[];
}

export interface GenerationStoryBrief {
  id?: string | null;
  concept_id?: string | null;
  format: string;
  title_left: string;
  title_right: string;
  left_character: "boy" | "girl";
  left_action: string;
  left_setting: string;
  left_props: string[];
  left_emotion: string;
  right_characters: Array<"boy" | "girl">;
  right_action: string;
  right_setting: string;
  right_props: string[];
  right_emotion: string;
  shared_environment: string;
  environmental_contrast: string;
  background_color: string;
  accent_color: string;
  camera_angle: string;
  execution_risks: string[];
  emotional_insight: string;
  brand_sensitive: boolean;
  comics?: Array<Record<string, unknown>>;
}

export interface GenerationQaFinding {
  category: string;
  check: string;
  status: "Pass" | "Warning" | "Fail";
  detail: string;
}

export interface ImageModelInfo {
  id: string;
  key?: string;
  selection_mode?: "lite" | "balanced" | "pro";
  display_name: string;
  power_label: "FAST" | "BALANCED" | "MAX";
  power_level: 1 | 2 | 3;
  description: string;
  recommended_for: string[];
  cost_tier: string;
  model_id?: string;
}

export interface GenerationEvent {
  id: string;
  run_id: string;
  timestamp: string;
  level: "info" | "warning" | "error";
  kind: string;
  message: string;
  data: {
    stage?: "story" | "compile" | "references" | "generate" | "layout" | "qa" | "repair" | "human_review";
    status?: "pending" | "active" | "complete" | "warning" | "failed" | "skipped";
    candidate?: string;
    candidate_status?: "waiting" | "working" | "complete" | "failed";
    completed?: number;
    total?: number;
    qa_status?: string;
    repair_step?: string;
    issue?: string;
    model?: ImageModelInfo;
    [key: string]: unknown;
  };
}

export interface GenerationCandidate {
  id: string;
  label: string;
  image_path: string | null;
  asset_url: string | null;
  original_image_path?: string | null;
  final_image_path?: string | null;
  final_asset_url?: string | null;
  model: string;
  model_display_name: string;
  model_power_label: "FAST" | "BALANCED" | "MAX";
  model_power_level: 1 | 2 | 3;
  model_description: string;
  model_cost_tier: string;
  runtime_ms: number | null;
  qa_status: "Pending" | "Pass" | "Warning" | "Fail" | "Unavailable";
  qa_summary: string;
  qa_findings: GenerationQaFinding[];
  rank: number | null;
  recommended: boolean;
  selected: boolean;
  repair_parent_id: string | null;
  repair_number?: number;
  estimated_cost: number | null;
  reported_cost: number | null;
  error?: { code: string; message: string; retryable: boolean } | null;
}

export interface GenerationRun {
  id: string;
  concept_id: string | null;
  concept_text: string;
  story_brief: GenerationStoryBrief;
  story_format: string;
  status: "draft" | "compiling" | "generating" | "reviewing" | "repairing" | "awaiting_human" | "approved" | "rejected" | "failed" | "cancelled";
  model_selection_mode: string;
  selected_model: string | null;
  selected_model_info?: ImageModelInfo | null;
  comparison_model_info?: ImageModelInfo[];
  selection_reason: string;
  candidate_count: number;
  candidates: GenerationCandidate[];
  selected_candidate_id: string | null;
  final_asset_url: string | null;
  final_image_path?: string | null;
  comic_asset_count?: number;
  started_at: string;
  completed_at: string | null;
  approved_at: string | null;
  runtime_ms: number | null;
  estimated_cost: number | null;
  reported_cost: number | null;
  warnings: string[];
  error: string | null;
  comparison: boolean;
  generation_recipe?: string[];
  prompt_record: { prompt_id: string; template: string; template_version: string; character_rule_version: string; failure_rule_version: string; created_at: string; prompt?: string };
}

export interface ImageGenerationSettings {
  provider: "google_gemini";
  default_selection: "automatic" | "lite" | "balanced" | "pro";
  candidate_count: number;
  default_aspect_ratio: string;
  default_resolution: string;
  demo_mode: boolean;
  developer_mode: boolean;
  enable_paid_generation: boolean;
  maximum_cost_per_run: number;
  daily_image_budget: number;
  monthly_image_budget: number;
  automatic_pro_usage: boolean;
  warn_at_percent: number;
  hard_stop_at_percent: number;
}

export interface Concept {
  id: string;
  format: string;
  title_pair: { left: string; right: string };
  left_scene: string;
  right_scene: string;
  emotional_insight: string;
  emotional_theme: string;
  category?: string;
  left_character: "boy" | "girl";
  left_character_action?: string;
  left_setting?: string;
  left_props?: string[];
  left_emotion?: string;
  right_characters?: "boy_and_girl";
  right_character_actions?: string;
  right_setting?: string;
  right_props?: string[];
  right_emotion?: string;
  shared_environment?: string;
  environmental_contrast?: string;
  prop_count?: number;
  scene_richness?: "Sparse" | "Balanced" | "Detailed";
  scene_warnings?: string[];
  migration_version?: 2;
  recommended_background_color: string;
  recommended_accent_color: string;
  recommended_camera_angle: string;
  brand_friendly: boolean;
  source?: string;
  status: string;
  score?: Score | null;
  created_at?: string;
  updated_at?: string;
  props?: string[];
  execution_risks?: string[];
  brand_placement_opportunities?: string[];
  why_someone_would_share?: string;
  notes?: string | null;
  novel_angle?: string;
  potential_product_category?: string | null;
  brand_categories?: string[];
  natural_product_placement?: string | null;
}

export interface Score {
  scores: Record<string, number>;
  directional_total: number;
  weakest_criterion: string;
  improvement_recommendation: string;
  relevant_social_learnings: string[];
  evaluation_label: string;
}

export interface Learning {
  learning_id: string;
  pattern: string;
  evidence_post_ids: string[];
  confidence: Confidence;
  metric_supported: boolean;
  hypothesis: string;
  recommended_use: string;
  avoid_overgeneralizing: string;
  last_updated: string;
  status: string;
}

export interface SocialPost {
  id: string;
  title: string;
  platform: string | null;
  post_date: string | null;
  views: number | null;
  shares: number | null;
  likes: number | null;
  comments: number | null;
  saves: number | null;
  format: string | null;
  emotional_theme: string | null;
  uploaded_asset_reference: string | null;
  rates: Record<string, number | null>;
  metric_completeness: { known: number; total: number; percent: number };
}

export interface PatternData {
  sample_size: number;
  top_by_views: Array<SocialPost & { _rank_value: number }>;
  top_by_shares: Array<SocialPost & { _rank_value: number }>;
  top_by_share_rate: Array<SocialPost & { _rank_value: number }>;
  themes: { value: string; count: number }[];
  formats: { value: string; count: number }[];
  backgrounds: { value: string; count: number }[];
  camera_angles: { value: string; count: number }[];
  prop_counts: { value: string; count: number }[];
  causation_warning: string;
}

export type SpriteCharacterType = "dinko" | "dinka" | "shared" | "prop" | "effect";
export type SpriteLoopMode = "loop" | "ping_pong" | "play_once" | "hold_last";
export type SpriteApprovalLevel = "Draft" | "Frame review" | "Animation review" | "Approved" | "Deprecated";

export interface SpriteCharacter {
  id: string;
  name: string;
  slug: string;
  character_type: SpriteCharacterType;
  official_reference_paths: string[];
  default_canvas_width: number;
  default_canvas_height: number;
  default_anchor_x: number;
  default_anchor_y: number;
  default_frame_rate: number;
  approved: boolean;
  locked: boolean;
  notes: string;
  animation_count?: number;
  reference_status?: string;
  animations?: SpriteAnimation[];
}

export interface SpriteFrame {
  id: string;
  character_id: string;
  animation_id: string;
  frame_index: number;
  image_path: string;
  asset_url: string;
  width: number;
  height: number;
  duration_ms: number;
  anchor_x: number;
  anchor_y: number;
  offset_x: number;
  offset_y: number;
  opacity: number;
  approved: boolean;
  validation_status: "pending" | "valid" | "warning" | "invalid";
  validation_warnings: string[];
  review_status: "Pass" | "Needs edit" | "Reject" | "Not reviewed";
  review_notes: string;
  transparent: boolean;
}

export interface SpriteAnimation {
  id: string;
  name: string;
  slug: string;
  character_id: string;
  character?: SpriteCharacter;
  category: string;
  description: string;
  frames: SpriteFrame[];
  frame_ids: string[];
  frame_count: number;
  frame_rate: number;
  duration_ms: number;
  loop: boolean;
  loop_mode: SpriteLoopMode;
  loop_start_frame?: number;
  loop_end_frame?: number | null;
  hold_first_frame_ms: number;
  hold_last_frame_ms: number;
  default_scale: number;
  expected_frame_count: number;
  default_anchor_x: number;
  default_anchor_y: number;
  approved: boolean;
  approval_level: SpriteApprovalLevel;
  tags: string[];
  required_layers: string[];
  optional_layers: string[];
  thumbnail_path: string | null;
  preview_path: string | null;
  status: "Frames needed" | "Draft" | "Needs review" | "Approved" | "Exported";
  validation_status: string;
  validation_checklist?: string[];
  technical_sample: boolean;
  notes: string;
}

export interface SpriteLayer {
  id: string;
  layer_type: "background" | "dinko" | "dinka" | "shared" | "prop" | "effect" | "foreground" | "text";
  animation_id: string | null;
  label: string;
  x: number;
  y: number;
  scale: number;
  start_offset_ms: number;
  z_index: number;
  visible: boolean;
  settings: Record<string, unknown>;
}

export interface SpriteComposition {
  id: string;
  name: string;
  preset: string | null;
  canvas_width: number;
  canvas_height: number;
  background_color: string;
  loop_duration_ms: number;
  layers: SpriteLayer[];
  notes: string;
  status: string;
}

export interface SpriteExport {
  id: string;
  animation_id: string;
  animation_name: string;
  character: string;
  export_format: string;
  path: string;
  metadata_path: string;
  asset_url: string;
  metadata_url: string;
  frame_count: number;
  frame_width: number;
  frame_height: number;
  sheet_width: number;
  sheet_height: number;
  padding: number;
  official_use: boolean;
  warning: string | null;
  created_at: string;
}

export interface SharedInteraction {
  id: string;
  name: string;
  dinko_animation_id: string;
  dinka_animation_id: string;
  shared_frame_rate: number;
  shared_duration: number;
  dinko_offset: { x: number; y: number };
  dinka_offset: { x: number; y: number };
  loop_mode: SpriteLoopMode;
  approved: boolean;
  notes: string;
}

export interface ProviderBudgetSettings {
  enable_paid_provider_calls: boolean;
  maximum_estimated_cost_per_run: number;
  daily_provider_budget: number;
  monthly_provider_budget: number;
  maximum_handles_per_refresh: number;
  maximum_posts_per_handle: number;
  maximum_provider_requests_per_run: number;
  maximum_retries: number;
  require_confirmation_above_estimated_cost: number;
  automatically_pause_at_80_percent: boolean;
  hard_stop_at_100_percent: boolean;
  allow_paid_overage: boolean;
  schedule_enabled: boolean;
  schedule_frequency: "Daily" | "Every 3 days" | "Weekly";
  connection_timeout_seconds: number;
  read_timeout_seconds: number;
  actor_run_timeout_seconds: number;
  download_timeout_seconds: number;
}

export interface ProviderUsageSummary {
  daily_used: number;
  daily_remaining: number;
  monthly_used: number;
  monthly_remaining: number;
  monthly_budget: number;
  percent_used: number;
  percent_remaining: number;
  approaching_limit: boolean;
  hard_limit_reached: boolean;
}

export interface SocialProviderStatus {
  provider?: string;
  name?: string;
  platform?: string;
  state: string;
  configured: boolean;
  masked_token?: string | null;
  instagram_actor_id?: string;
  tiktok_actor_id?: string;
  circuit_state?: string;
  paused?: boolean;
  message?: string;
  last_success_at?: string | null;
  last_error_code?: string | null;
  budget?: ProviderUsageSummary;
  platforms?: Record<"instagram" | "tiktok", ActorPlatformStatus>;
}

export interface ActorPlatformStatus {
  platform: "instagram" | "tiktok";
  enabled: boolean;
  source: "recommended" | "override";
  actor_override: string;
  last_verified_at: string | null;
  verification_status: string;
  actor_name: string;
  actor_owner: string;
  pricing_summary: string;
  ready?: boolean;
  status?: string;
  message?: string;
}

export interface MonitoredHandle {
  id: string;
  platform: "instagram" | "tiktok";
  username: string;
  canonical_url: string;
  display_name: string | null;
  category: string;
  enabled: boolean;
  provider: string;
  posts_per_refresh: number;
  refresh_frequency: "Off" | "Daily" | "Every 3 days" | "Weekly";
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  follower_count: number | null;
}

export interface ProviderPreflight {
  handles: number;
  platforms: string[];
  posts_per_handle?: number;
  maximum_posts: number;
  expected_provider_runs?: number;
  estimated_cost_low: number | null;
  estimated_cost_high: number | null;
  estimated_cost_label?: string;
  daily_budget_remaining?: number;
  monthly_budget_remaining?: number;
  monthly_percent_used?: number;
  requires_confirmation: boolean;
  can_run: boolean;
  warnings: string[];
  hard_stops: string[];
  provider_health?: string;
  provider_configured?: boolean;
  manual_import_available?: boolean;
}

export interface CompetitorPost {
  id: string;
  handle_id: string;
  platform: "instagram" | "tiktok";
  platform_post_id: string;
  post_url: string | null;
  caption: string | null;
  posted_at: string | null;
  media_type: string | null;
  remote_thumbnail_url: string | null;
  media_url?: string | null;
  carousel_item_count?: number | null;
  view_count: number | null;
  like_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  creative_attributes: Record<string, unknown>;
  handle: Partial<MonitoredHandle>;
  performance: {
    primary_metric: string | null;
    account_median: number | null;
    account_average: number | null;
    percentile_rank: number | null;
    multiplier: number | null;
    sample_size: number;
  };
  metric_completeness: { known: number; total: number; percent: number };
  snapshot_count: number;
  velocity_message: string | null;
}

export interface CompetitorLearning {
  id: string;
  classification: string;
  pattern: string;
  measured_fact: string;
  hypothesis: string;
  recommendation: string;
  data_limitation: string;
  confidence: "High" | "Medium" | "Low";
  sample_size: number;
  evidence_post_ids: string[];
  status: "Pending" | "Approved" | "Rejected";
}

export interface CompetitorDirection {
  id: string;
  signal: string;
  source_pattern: string;
  reusable_principle: string;
  must_not_copy: string;
  dinkly_emotional_angle: string;
  title_pair: { left: string; right: string };
  left_scene: string;
  right_scene: string;
  shared_setting: string;
  purposeful_props: string[];
  pastel_background: string;
  accent_color: string;
  execution_risks: string[];
  why_original: string;
  why_someone_may_share: string;
  confidence: "High" | "Medium" | "Low";
  status: string;
  concept_id: string | null;
}

export interface AgentRun {
  id: string;
  agent?: string;
  display_agent?: string;
  kind: string;
  status: string;
  summary: Record<string, unknown>;
  warnings: string[];
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AgentEvent {
  id: string;
  run_id: string;
  timestamp: string;
  level: string;
  kind: string;
  message: string;
  data: Record<string, unknown>;
}
