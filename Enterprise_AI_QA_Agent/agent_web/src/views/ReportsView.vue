<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../services/api";
import { formatServerDateTime, serverDateTimestamp } from "../utils/datetime";
import type {
  SessionDetail,
  SessionSummary,
  ToolArtifactRecord,
  VerificationResult,
  WorkerDispatchRecord,
} from "../types";

interface ReportEntry {
  session: SessionDetail;
  artifacts: ToolArtifactRecord[];
  verifications: VerificationResult[];
  workerDispatches: WorkerDispatchRecord[];
  reportMeta: Record<string, unknown>;
  reportSession: SessionDetail | null;
  reportArtifacts: ToolArtifactRecord[];
}

interface ReportsCachePayload {
  cachedAt: string;
  selectedSessionId: string;
  reports: ReportEntry[];
}

const REPORTS_CACHE_KEY = "enterprise-ai-qa:reports-cache";
const REPORTS_CACHE_TTL_MS = 2 * 60 * 1000;

let reportsMemoryCache: ReportsCachePayload | null = null;

const loading = ref(false);
const error = ref("");
const selectedSessionId = ref("");
const reports = ref<ReportEntry[]>([]);

const selectedReport = computed(() => {
  if (!reports.value.length) {
    return null;
  }
  return (
    reports.value.find((item) => item.session.id === selectedSessionId.value) ??
    reports.value[0]
  );
});

const selectedReportBody = computed(() => {
  const report = selectedReport.value;
  if (!report) {
    return "";
  }
  const primaryArtifact = [...report.reportArtifacts, ...report.artifacts].find((item) =>
    ["report_markdown", "report_html"].includes(item.artifact_type),
  );
  const inlineContent = artifactInlineContent(primaryArtifact);
  if (inlineContent) {
    return inlineContent;
  }
  return String(report.reportMeta.summary || "").trim();
});

const selectedWorkerSummary = computed(() => {
  const report = selectedReport.value;
  if (!report) {
    return { running: 0, completed: 0, failed: 0, total: 0 };
  }
  const summary = { running: 0, completed: 0, failed: 0, total: report.workerDispatches.length };
  for (const worker of report.workerDispatches) {
    const status = String(worker.status || "").trim();
    if (status === "failed") {
      summary.failed += 1;
    } else if (status === "running" || status === "waiting_approval") {
      summary.running += 1;
    } else {
      summary.completed += 1;
    }
  }
  return summary;
});

function workerDispatchesFromSession(session: SessionDetail): WorkerDispatchRecord[] {
  const rawValue = session.metadata?.worker_dispatches;
  if (!Array.isArray(rawValue)) {
    return [];
  }
  return rawValue.filter(
    (item): item is WorkerDispatchRecord =>
      typeof item === "object" && item !== null,
  );
}

function artifactInlineContent(artifact?: ToolArtifactRecord | null): string {
  if (!artifact) {
    return "";
  }
  const metadata = artifact.metadata || {};
  const inlineText = metadata.__content_text;
  return typeof inlineText === "string" ? inlineText.trim() : "";
}

function readReportMeta(session: SessionDetail): Record<string, unknown> {
  const rawValue = session.metadata?.code_review_report;
  if (!rawValue || typeof rawValue !== "object" || Array.isArray(rawValue)) {
    return {};
  }
  return rawValue as Record<string, unknown>;
}

function reportSessionIdFromEntry(entry: {
  session: SessionDetail;
  workerDispatches: WorkerDispatchRecord[];
  reportMeta: Record<string, unknown>;
}): string {
  const explicit = String(entry.reportMeta.report_session_id || "").trim();
  if (explicit) {
    return explicit;
  }
  const completionWorker = entry.workerDispatches.find((item) =>
    Boolean((item as Record<string, unknown>).is_completion_worker),
  );
  return String(completionWorker?.child_session_id || "").trim();
}

function gradeForSession(entry: ReportEntry): string {
  if (entry.session.status === "failed") return "较差";
  if (entry.session.status === "running" || entry.session.status === "waiting_approval") return "进行中";
  if (entry.verifications.some((item) => item.status === "failed")) return "需关注";
  if (entry.verifications.some((item) => item.status === "partial")) return "需关注";
  return "良好";
}

function gradeTone(grade: string): string {
  if (grade === "C") return "badge-red";
  if (grade === "B") return "badge-yellow";
  return "badge-green";
}

function statusLabel(status: string): string {
  if (status === "waiting_approval") return "待审批";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "running") return "运行中";
  if (status === "interrupted") return "已中断";
  return "空闲";
}

function artifactLabel(artifact: ToolArtifactRecord): string {
  return artifact.label || artifact.artifact_type || "产物";
}

function formatDateTime(value: string): string {
  return formatServerDateTime(value, value);
}

function normalizeSelectedSessionId(nextReports: ReportEntry[], preferredId = ""): string {
  const preferred = String(preferredId || "").trim();
  if (!nextReports.length) {
    return "";
  }
  if (preferred && nextReports.some((item) => item.session.id === preferred)) {
    return preferred;
  }
  return nextReports[0]?.session.id || "";
}

function isReportsCacheFresh(payload: ReportsCachePayload | null): boolean {
  if (!payload) {
    return false;
  }
  const cachedAt = Date.parse(String(payload.cachedAt || ""));
  if (Number.isNaN(cachedAt)) {
    return false;
  }
  return Date.now() - cachedAt <= REPORTS_CACHE_TTL_MS;
}

function readReportsCache(): ReportsCachePayload | null {
  if (reportsMemoryCache) {
    return reportsMemoryCache;
  }
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(REPORTS_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as ReportsCachePayload;
    if (!parsed || !Array.isArray(parsed.reports)) {
      return null;
    }
    reportsMemoryCache = parsed;
    return parsed;
  } catch {
    return null;
  }
}

function writeReportsCache(nextReports: ReportEntry[], nextSelectedSessionId: string) {
  const payload: ReportsCachePayload = {
    cachedAt: new Date().toISOString(),
    selectedSessionId: normalizeSelectedSessionId(nextReports, nextSelectedSessionId),
    reports: nextReports,
  };
  reportsMemoryCache = payload;
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(REPORTS_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore storage quota / availability errors and keep memory cache only.
  }
}

function hydrateReportsFromCache(payload: ReportsCachePayload) {
  reports.value = payload.reports;
  selectedSessionId.value = normalizeSelectedSessionId(payload.reports, payload.selectedSessionId);
}

async function loadReports(forceRefresh = false) {
  const cached = forceRefresh ? null : readReportsCache();
  if (cached) {
    hydrateReportsFromCache(cached);
    if (isReportsCacheFresh(cached)) {
      return;
    }
  }

  loading.value = true;
  error.value = "";
  try {
    const summaries = await api.listSessions();
    const relevantSummaries = summaries
      .filter((item: SessionSummary) => item.mode_key === "code_review")
      .sort((a, b) => serverDateTimestamp(b.updated_at) - serverDateTimestamp(a.updated_at))
      .slice(0, 12);

    const details = await Promise.all(
      relevantSummaries.map((item) => api.getSession(item.id)),
    );

    const baseEntries = await Promise.all(
      details.map(async (session) => {
        const [artifacts, verifications] = await Promise.all([
          api.listArtifacts(session.id),
          api.listVerifications(session.id),
        ]);
        return {
          session,
          artifacts,
          verifications: verifications.verification_results || [],
          workerDispatches: workerDispatchesFromSession(session),
          reportMeta: readReportMeta(session),
        };
      }),
    );

    const fullEntries = await Promise.all(
      baseEntries.map(async (entry) => {
        const reportSessionId = reportSessionIdFromEntry(entry);
        if (!reportSessionId || reportSessionId === entry.session.id) {
          return {
            ...entry,
            reportSession: null,
            reportArtifacts: [],
          };
        }
        try {
          const [reportSession, reportArtifacts] = await Promise.all([
            api.getSession(reportSessionId),
            api.listArtifacts(reportSessionId),
          ]);
          return {
            ...entry,
            reportSession,
            reportArtifacts,
          };
        } catch {
          return {
            ...entry,
            reportSession: null,
            reportArtifacts: [],
          };
        }
      }),
    );

    reports.value = fullEntries;
    selectedSessionId.value = normalizeSelectedSessionId(fullEntries, selectedSessionId.value);
    writeReportsCache(fullEntries, selectedSessionId.value);
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "加载报告失败。";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadReports();
});
</script>

<template>
  <section class="view-page report-page">
    <header class="page-head">
      <div class="head-content">
        <h2>报告中心</h2>
        <p class="head-desc">
          查看代码审批会话、辩论总结和最终报告产物。
        </p>
      </div>
      <div class="head-actions">
        <button class="primary-btn" :disabled="loading" @click="loadReports(true)">
          <i class="fa-solid fa-rotate-right"></i>
          刷新
        </button>
      </div>
    </header>

    <div v-if="error" class="empty-state error-state">
      <strong>报告加载失败。</strong>
      <p>{{ error }}</p>
    </div>

    <div v-else-if="loading && !reports.length" class="empty-state">
      <strong>正在加载报告...</strong>
      <p>工作台正在汇总最近的代码审批会话。</p>
    </div>

    <div v-else-if="!reports.length" class="empty-state">
      <strong>暂时还没有代码审批报告。</strong>
      <p>发起一次代码审批后，已完成的报告会显示在这里。</p>
    </div>

    <div v-else class="report-layout">
      <aside class="report-sidebar">
        <div class="sidebar-header">
          <h3>代码审批批次</h3>
        </div>
        <div class="batch-list">
          <article
            v-for="entry in reports"
            :key="entry.session.id"
            class="batch-item"
            :class="{ active: entry.session.id === selectedSessionId }"
            @click="selectedSessionId = entry.session.id"
          >
            <div class="batch-item-header">
              <span class="batch-id">#{{ entry.session.id.slice(0, 8) }}</span>
              <span class="badge" :class="gradeTone(gradeForSession(entry))">
                {{ gradeForSession(entry) }}
              </span>
            </div>
            <p class="batch-title">{{ entry.session.title }}</p>
            <p class="batch-meta mono">
              {{ entry.session.mode_key }} · {{ formatDateTime(entry.session.updated_at) }}
            </p>
            <div class="batch-stats">
              <span class="stat pass">
                <i class="fa-solid fa-layer-group"></i>
                {{ entry.workerDispatches.length }} 个任务
              </span>
              <span class="stat fail">
                <i class="fa-solid fa-shield-halved"></i>
                {{ entry.verifications.length }} 条校验
              </span>
            </div>
          </article>
        </div>
      </aside>

      <main v-if="selectedReport" class="report-detail">
        <div class="detail-header">
          <div class="detail-title">
            <div class="title-row">
              <h3>{{ selectedReport.session.title }}</h3>
              <span class="grade-box">{{ gradeForSession(selectedReport) }}</span>
            </div>
            <p class="detail-desc">
              <i class="fa-solid fa-robot"></i>
              {{ statusLabel(selectedReport.session.status) }} ·
              {{ formatDateTime(selectedReport.session.updated_at) }}
            </p>
          </div>
        </div>

        <div class="report-kpis">
          <article class="kpi-card">
            <span class="kpi-label">审查任务</span>
            <strong>{{ selectedWorkerSummary.total }}</strong>
            <p>
              已完成 {{ selectedWorkerSummary.completed }} /
              运行中 {{ selectedWorkerSummary.running }} /
              失败 {{ selectedWorkerSummary.failed }}
            </p>
          </article>
          <article class="kpi-card">
            <span class="kpi-label">报告产物</span>
            <strong>{{ selectedReport.reportArtifacts.length + selectedReport.artifacts.length }}</strong>
            <p>合并展示父会话和总结会话的产物。</p>
          </article>
          <article class="kpi-card">
            <span class="kpi-label">报告会话</span>
            <strong>{{ selectedReport.reportSession ? "已就绪" : "待生成" }}</strong>
            <p>
              {{
                selectedReport.reportSession
                  ? `#${selectedReport.reportSession.id.slice(0, 8)}`
                  : "总结 Agent 尚未完成。"
              }}
            </p>
          </article>
        </div>

        <div class="detail-content">
          <section class="content-section">
            <div class="section-header">
              <h4>摘要</h4>
              <span class="subtitle mono">code_review_report</span>
            </div>
            <div class="summary-card">
              <p v-if="selectedReportBody" class="summary-body">{{ selectedReportBody }}</p>
              <p v-else class="summary-body muted">
                暂无内联报告正文，报告会话可能仍在运行中。
              </p>
            </div>
          </section>

          <section class="content-section">
            <div class="section-header">
              <h4>审查任务</h4>
              <span class="subtitle mono">评审辩论会话</span>
            </div>
            <div class="worker-grid">
              <article
                v-for="worker in selectedReport.workerDispatches"
                :key="worker.task_id"
                class="worker-card"
              >
                <div class="worker-card-head">
                  <strong>{{ worker.agent_key }}</strong>
                  <span class="worker-status" :class="`worker-status-${worker.status}`">
                    {{ statusLabel(worker.status) }}
                  </span>
                </div>
                <p>{{ worker.description }}</p>
                <p class="worker-meta mono">
                  task={{ worker.task_id.slice(0, 8) }}
                  <span v-if="worker.child_session_id">
                    · session={{ worker.child_session_id.slice(0, 8) }}
                  </span>
                </p>
              </article>
            </div>
          </section>

          <section class="content-section">
            <div class="section-header">
              <h4>报告产物</h4>
              <span class="subtitle mono">已存储的报告输出</span>
            </div>
            <div class="artifact-list">
              <article
                v-for="artifact in [...selectedReport.reportArtifacts, ...selectedReport.artifacts]"
                :key="artifact.id"
                class="artifact-card"
              >
                <div class="artifact-head">
                  <strong>{{ artifactLabel(artifact) }}</strong>
                  <span class="artifact-type mono">{{ artifact.artifact_type }}</span>
                </div>
                <p class="artifact-path mono">{{ artifact.path }}</p>
                <pre v-if="artifactInlineContent(artifact)" class="artifact-preview">{{
                  artifactInlineContent(artifact)
                }}</pre>
              </article>
            </div>
          </section>

          <section class="content-section">
            <div class="section-header">
              <h4>校验结果</h4>
              <span class="subtitle mono">会话校验结果</span>
            </div>
            <div v-if="selectedReport.verifications.length" class="verification-list">
              <article
                v-for="verification in selectedReport.verifications"
                :key="verification.id"
                class="verification-card"
              >
                <div class="verification-head">
                  <strong>{{ verification.verifier }}</strong>
                  <span class="worker-status" :class="`worker-status-${verification.status}`">
                    {{ verification.status }}
                  </span>
                </div>
                <p>{{ verification.summary }}</p>
              </article>
            </div>
            <div v-else class="summary-card">
              <p class="summary-body muted">当前会话还没有记录校验结果。</p>
            </div>
          </section>
        </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px 32px;
  background: var(--bg);
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.head-content h2 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 6px 0;
  letter-spacing: -0.02em;
}

.head-desc {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

.report-layout {
  display: flex;
  flex: 1;
  gap: 24px;
  min-height: 0;
}

.report-sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  padding-right: 24px;
  flex-shrink: 0;
}

.sidebar-header h3 {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin: 0 0 16px 0;
}

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.batch-item {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  cursor: pointer;
  transition: all 0.2s ease;
}

.batch-item:hover {
  background: var(--surface-muted);
}

.batch-item.active {
  background: var(--surface);
  border-color: var(--border-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.batch-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.batch-id,
.batch-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
}

.batch-title {
  margin: 0 0 10px 0;
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}

.badge-green {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.badge-yellow {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}

.badge-red {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.batch-meta {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 12px 0;
}

.batch-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  font-weight: 500;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat.pass {
  color: #16a34a;
}

.stat.fail {
  color: #dc2626;
}

.report-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-right: 8px;
}

.detail-header {
  margin-bottom: 24px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.title-row h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.grade-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #111827;
  color: white;
  font-weight: 700;
  font-size: 13px;
  padding: 0 10px;
}

.detail-desc {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.report-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.kpi-card,
.summary-card,
.worker-card,
.artifact-card,
.verification-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}

.kpi-label {
  display: block;
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}

.kpi-card strong {
  font-size: 22px;
}

.kpi-card p,
.summary-body,
.worker-card p,
.artifact-card p,
.verification-card p {
  margin: 8px 0 0 0;
  line-height: 1.6;
  color: var(--text);
}

.summary-body {
  white-space: pre-wrap;
}

.muted {
  color: var(--muted);
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.section-header h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--muted);
}

.worker-grid,
.artifact-list,
.verification-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.worker-card-head,
.artifact-head,
.verification-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.worker-meta,
.artifact-path,
.artifact-type {
  color: var(--muted);
  font-size: 12px;
}

.artifact-preview {
  margin: 12px 0 0 0;
  padding: 12px;
  border-radius: 10px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  overflow: auto;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.5;
}

.worker-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.worker-status-completed,
.worker-status-passed {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.worker-status-running,
.worker-status-waiting_approval,
.worker-status-partial {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.worker-status-failed {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.empty-state {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 240px;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 16px;
  background: var(--surface);
  color: var(--muted);
}

.error-state {
  color: #dc2626;
}

.mono {
  font-family: var(--font-mono, monospace);
}

@media (max-width: 1080px) {
  .report-layout {
    flex-direction: column;
  }

  .report-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border);
    padding-right: 0;
    padding-bottom: 20px;
  }

  .report-kpis {
    grid-template-columns: 1fr;
  }
}
</style>
