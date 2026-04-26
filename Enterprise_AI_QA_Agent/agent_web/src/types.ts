export type SessionStatus =
  | "idle"
  | "running"
  | "waiting_approval"
  | "interrupted"
  | "completed"
  | "failed";

export type SessionMode =
  | "normal"
  | "coordinator"
  | "resumed"
  | "direct_connect"
  | "remote"
  | "assistant_viewer"
  | "background_task";

export type RuntimeMode = "interactive" | "headless" | "background";
export type ModeKey =
  | "default"
  | "code_review"
  | "ui_automation"
  | "api_testing"
  | "security_testing"
  | "performance_testing"
  | "smoke_testing";

export type MessageRole = "system" | "user" | "assistant" | "tool" | "event";

export interface HealthResponse {
  status: string;
  name: string;
  environment: string;
  memory_backend?: string;
  session_backend?: string;
  tool_job_backend?: string;
  ui_graph_backend?: string;
  knowledge_enabled?: boolean;
  memory_target?: string;
  knowledge_target?: string;
}

export type ServiceCheckStatus = "online" | "degraded" | "offline";

export interface ServiceCheckItem {
  key: string;
  label: string;
  status: ServiceCheckStatus;
  detail: string;
  meta?: string;
}

export interface SystemStatusSummary {
  label: string;
  tone: ServiceCheckStatus;
  checks: ServiceCheckItem[];
  onlineCount: number;
  totalCount: number;
}

export interface ToolDescriptor {
  key: string;
  name: string;
  description: string;
  category: string;
  permission_level?: "safe" | "ask" | "restricted";
  supports_streaming?: boolean;
  enabled_by_default?: boolean;
  tags?: string[];
}

export interface SkillDescriptor {
  key: string;
  name: string;
  summary: string;
  description: string;
  recommended_agents: string[];
  tags: string[];
  installed?: boolean;
  managed_root?: string;
  path?: string;
  source?: string;
  references?: string[];
  content?: string;
}

export interface SkillInstallRequest {
  source_path?: string | null;
  url?: string | null;
  key?: string | null;
  overwrite?: boolean;
}

export interface SkillUploadRequest {
  filename: string;
  content_base64: string;
  key?: string | null;
  overwrite?: boolean;
}

export type SkillMarketplaceSource = "anthropic" | "skillsmp";

export interface SkillMarketplaceItem {
  source: SkillMarketplaceSource | string;
  id: string;
  key?: string;
  name: string;
  description?: string;
  tags?: string[];
  url?: string;
  content?: string;
  metadata?: Record<string, unknown>;
}

export interface SkillMarketplaceSearchResponse {
  source: SkillMarketplaceSource | string;
  query: string;
  items: SkillMarketplaceItem[];
  count: number;
}

export interface SkillMarketplaceInstallRequest {
  source: SkillMarketplaceSource | string;
  skill_id: string;
  url?: string | null;
  key?: string | null;
  overwrite?: boolean;
}

export interface SkillBulkInstallResponse {
  ok: boolean;
  status: string;
  summary: string;
  installed_count: number;
  failed_count: number;
  items: SkillDescriptor[];
  failed: Array<{ key: string; source: string; error: string }>;
}

export interface SkillUpsertRequest {
  content: string;
}

export interface AgentDescriptor {
  key: string;
  name: string;
  role: string;
  summary: string;
  description: string;
  supported_tools: string[];
  supported_skills: string[];
  supported_models: string[];
  default_model?: string | null;
  tags: string[];
}

export interface ModeDescriptor {
  key: ModeKey | string;
  name: string;
  summary: string;
  description: string;
  category: string;
  is_test_mode: boolean;
  default_agent_key: string;
  allowed_agent_keys: string[];
  default_skill_keys: string[];
  registered_tool_keys: string[];
  harness_key: string;
  placeholder: boolean;
  tags: string[];
}

export interface ModelDescriptor {
  key: string;
  name: string;
  provider: string;
  summary: string;
  supports_tools: boolean;
  supports_vision: boolean;
  supports_reasoning: boolean;
  tags: string[];
}

export interface ModelConfigPublic {
  id?: number | null;
  key: string;
  name: string;
  provider: string;
  transport: string;
  api_base_url: string;
  description: string;
  supports_tools: boolean;
  supports_vision: boolean;
  supports_reasoning: boolean;
  is_active: boolean;
  is_default: boolean;
  temperature?: number | null;
  max_tokens: number;
  has_secret: boolean;
  capabilities: ModelCapabilities;
  capability_overrides: ModelCapabilitiesOverride;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ModelCapabilities {
  text_input: boolean;
  text_output: boolean;
  tool_calling: boolean;
  vision: boolean;
  multi_image: boolean;
  file_input: boolean;
  pdf_input: boolean;
  reasoning: boolean;
  json_mode: boolean;
  streaming: boolean;
  parallel_tool_calls: boolean;
  image_url_input: boolean;
  image_base64_input: boolean;
}

export interface ModelCapabilitiesOverride {
  text_input?: boolean | null;
  text_output?: boolean | null;
  tool_calling?: boolean | null;
  vision?: boolean | null;
  multi_image?: boolean | null;
  file_input?: boolean | null;
  pdf_input?: boolean | null;
  reasoning?: boolean | null;
  json_mode?: boolean | null;
  streaming?: boolean | null;
  parallel_tool_calls?: boolean | null;
  image_url_input?: boolean | null;
  image_base64_input?: boolean | null;
}

export interface ModelConfigUpdateRequest {
  model_name: string;
  provider: string;
  transport?: string | null;
  base_url: string;
  api_key?: string | null;
  is_active: boolean;
  use_provider_defaults?: boolean | null;
  capability_overrides: ModelCapabilitiesOverride;
}

export interface ModelConfigActionResponse {
  ok: boolean;
  message: string;
  item?: ModelConfigPublic | null;
}

export interface ModelConfigConnectionTestResponse {
  ok: boolean;
  message: string;
  item: ModelConfigPublic;
  provider: string;
  api_base_url: string;
  latency_ms?: number | null;
  preview?: string | null;
}

export interface EmailConfigPublic {
  id: number;
  config_name: string;
  provider: string;
  enabled: boolean;
  is_default: boolean;
  sender_email: string;
  test_email?: string | null;
  test_mode: boolean;
  description?: string | null;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_username?: string | null;
  extra_config?: Record<string, unknown>;
  has_api_key: boolean;
  has_secret_key: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface EmailConfigCreateRequest {
  config_name: string;
  provider: string;
  enabled: boolean;
  is_default: boolean;
  api_key?: string | null;
  secret_key?: string | null;
  sender_email: string;
  test_email?: string | null;
  test_mode: boolean;
  description?: string | null;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_username?: string | null;
  extra_config?: Record<string, unknown>;
}

export interface EmailConfigUpdateRequest {
  config_name: string;
  provider: string;
  enabled: boolean;
  is_default: boolean;
  api_key?: string | null;
  secret_key?: string | null;
  sender_email: string;
  test_email?: string | null;
  test_mode: boolean;
  description?: string | null;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_username?: string | null;
  extra_config?: Record<string, unknown>;
}

export interface EmailConfigActionResponse {
  ok: boolean;
  message: string;
  item?: EmailConfigPublic | null;
}

export interface EmailConfigConnectionTestResponse {
  ok: boolean;
  message: string;
  item: EmailConfigPublic;
  smtp_host?: string | null;
  smtp_port?: number | null;
  latency_ms?: number | null;
  preview?: string | null;
}

export interface ToolApprovalRequest {
  id: string;
  session_id: string;
  tool_key: string;
  tool_name: string;
  reason: string;
  status: "pending" | "approved" | "denied";
  created_at: string;
  resolved_at?: string | null;
  decision_note?: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkerDispatchRecord {
  task_id: string;
  child_session_id?: string;
  agent_key: string;
  model_key?: string;
  description: string;
  status: string;
  completed_at?: string;
}

export interface WorkerFailureReason {
  agent_key?: string;
  description?: string;
  reason?: string;
  timestamp?: string;
}

export interface WorkerFailureGuard {
  turn_id?: string;
  count?: number;
  last_error?: string;
  recent_errors?: WorkerFailureReason[];
  blocked?: boolean;
}

export interface SessionSnapshot {
  id: string;
  session_id: string;
  version: number;
  stage: string;
  created_at: string;
  graph_state: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface SessionDetail {
  id: string;
  title: string;
  status: SessionStatus;
  session_mode: SessionMode;
  runtime_mode: RuntimeMode;
  mode_key: ModeKey | string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  event_count: number;
  snapshot_count: number;
  preferred_model?: string | null;
  selected_agent?: string | null;
  pending_approvals: ToolApprovalRequest[];
  last_snapshot?: SessionSnapshot | null;
  control_state: string;
  is_resumable: boolean;
  is_interrupted: boolean;
  replay_available: boolean;
  verification_results: VerificationResult[];
  metadata: Record<string, unknown>;
}

export interface PendingInputPayload {
  content?: string;
  submit_mode?: string;
  command_name?: string | null;
  message_kind?: string;
}

export interface PendingInputQueueEntry {
  id: string;
  created_at: string;
  busy_status: string;
  queue_behavior: string;
  interrupt_policy: string;
  reason: string;
  payload: PendingInputPayload;
  metadata: Record<string, unknown>;
}

export type SessionWatcherPhase =
  | "idle"
  | "running"
  | "waiting_approval"
  | "interrupted"
  | "failed"
  | "completed";

export interface ExecutionEvent {
  type: string;
  session_id: string;
  timestamp: string;
  payload: Record<string, string | number | boolean | null | undefined>;
}

export interface ConversationResponse {
  session: SessionDetail;
  output: ChatMessage;
  events: ExecutionEvent[];
}

export interface SessionReplayResponse {
  session_id: string;
  control_state: string;
  latest_snapshot?: SessionSnapshot | null;
  events: ExecutionEvent[];
  metadata: Record<string, unknown>;
}

export interface ToolExecutionSummary {
  call_id: string;
  job_id?: string | null;
  tool_key: string;
  tool_name: string;
  status: string;
  summary: string;
  trace_id?: string | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  approval_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export type ToolJobStatus =
  | "queued"
  | "running"
  | "waiting_approval"
  | "resume_requested"
  | "retry_requested"
  | "completed"
  | "partial"
  | "failed"
  | "denied"
  | "cancelled";

export interface ToolArtifactRecord {
  id: string;
  tool_job_id: string;
  session_id: string;
  turn_id: string;
  trace_id: string;
  tool_key: string;
  artifact_type: string;
  label?: string | null;
  path: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface ToolJobRecord {
  id: string;
  session_id: string;
  turn_id: string;
  trace_id: string;
  call_id: string;
  tool_key: string;
  tool_name: string;
  status: ToolJobStatus;
  attempt: number;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
  summary: string;
  error_message?: string | null;
  artifact_count: number;
  created_at: string;
  updated_at: string;
  heartbeat_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface ToolJobDetail extends ToolJobRecord {
  artifacts: ToolArtifactRecord[];
}

export type VerificationStatus = "passed" | "failed" | "partial" | "not_run";

export interface VerificationEvidence {
  source_type: string;
  source_id: string;
  label: string;
  detail: string;
  metadata: Record<string, unknown>;
}

export interface VerificationResult {
  id: string;
  session_id: string;
  turn_id: string;
  trace_id: string;
  verifier: string;
  status: VerificationStatus;
  summary: string;
  assertion_count: number;
  passed_count: number;
  failed_count: number;
  evidence: VerificationEvidence[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SessionVerificationResponse {
  session_id: string;
  verification_results: VerificationResult[];
  metadata: Record<string, unknown>;
}

export interface KnowledgeProjectSummary {
  project_scope: string;
  page_count: number;
  element_count: number;
  entity_count: number;
  edge_count: number;
  latest_updated_at?: string | null;
}

export interface KnowledgeGraphSummary {
  project_scope: string;
  page_count: number;
  element_count: number;
  entity_count: number;
  edge_count: number;
  relation_counts: Record<string, number>;
  latest_updated_at?: string | null;
}

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  kind: string;
  summary: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeGraphResponse {
  summary: KnowledgeGraphSummary;
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}

export interface KnowledgeProjectDeleteResponse {
  ok: boolean;
  project_scope: string;
  deleted_counts: Record<string, number>;
  message: string;
}
