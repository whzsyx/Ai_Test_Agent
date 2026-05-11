/**
 * API Testing Mode frontend type definitions.
 *
 * These types describe the structured output from the api-test-runner tool
 * that the frontend can use to render specialized UI components.
 */

// ---------------------------------------------------------------------------
// Pending Selection (returned when user input is needed)
// ---------------------------------------------------------------------------

export interface ApiTestingPendingSelection {
  kind: "project" | "endpoint_scope" | "endpoints" | "credential";
  prompt: string;
  options: ApiTestingSelectionOption[];
  recommended_option_id: string;
  allow_free_text: boolean;
  notes: string[];
}

export interface ApiTestingSelectionOption {
  id: string;
  label: string;
  value: string;
  description?: string;
  recommended?: boolean;
  // Project-specific fields.
  project_name?: string;
  project_url?: string;
  doc_count?: number;
  endpoint_count?: number;
  score?: number;
  // Endpoint-specific fields.
  method?: string;
  path?: string;
  summary?: string;
  capability?: string;
  is_core?: boolean;
}

// ---------------------------------------------------------------------------
// Campaign Report (returned after execution)
// ---------------------------------------------------------------------------

export interface ApiTestingReport {
  campaign_id: string;
  project_name: string;
  summary: string;
  total_tasks: number;
  completed: number;
  failed: number;
  skipped: number;
  passed_checks: number;
  failed_checks: number;
  duration_ms: number;
  tasks: ApiTestingTaskSummary[];
  findings: string[];
  generated_at: string;
}

export interface ApiTestingTaskSummary {
  task_id: string;
  name: string;
  method: string;
  path: string;
  full_url: string;
  capability: string;
  status: "completed" | "failed" | "skipped" | "running" | "pending";
  response_status: number | null;
  duration_ms: number;
  check_count: number;
  checks_passed: number;
  checks_failed: number;
  error: string | null;
  checks: ApiTestingCheckResult[];
  evidence?: string;
}

export interface ApiTestingCheckResult {
  name: string;
  kind: string;
  passed: boolean;
  expected: unknown;
  actual: unknown;
  description: string;
}

// ---------------------------------------------------------------------------
// Tool Output (full api-test-runner response)
// ---------------------------------------------------------------------------

export interface ApiTestRunnerOutput {
  status: "completed" | "partial" | "failed";
  phase: string;
  summary: string;
  pending_selection?: ApiTestingPendingSelection;
  selected_project?: {
    project_name: string;
    project_url: string;
    doc_count: number;
    endpoint_count: number;
  };
  project_candidates?: Array<{
    project_name: string;
    project_url: string;
    doc_count: number;
    endpoint_count: number;
    score: number;
  }>;
  endpoint_count?: number;
  selected_endpoint_count?: number;
  campaign_id?: string;
  task_count?: number;
  report?: ApiTestingReport;
  report_markdown?: string;
  artifacts?: ApiTestingArtifact[];
  notes?: string[];
}

export interface ApiTestingArtifact {
  type: string;
  filename: string;
  content_type: string;
  label: string;
}

// ---------------------------------------------------------------------------
// Helper: detect if a tool output is from api-test-runner
// ---------------------------------------------------------------------------

export function isApiTestRunnerOutput(output: Record<string, unknown>): output is ApiTestRunnerOutput {
  return (
    typeof output.phase === "string" &&
    typeof output.summary === "string" &&
    "api_testing_state" in output
  );
}

export function hasApiTestingReport(output: ApiTestRunnerOutput): boolean {
  return output.status === "completed" && output.report != null;
}

export function hasApiTestingPendingSelection(output: ApiTestRunnerOutput): boolean {
  return output.status === "partial" && output.pending_selection != null;
}
