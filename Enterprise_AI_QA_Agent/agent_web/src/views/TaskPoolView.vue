<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { api } from "../services/api";
import type { SessionDetail, SessionSummary, WorkerDispatchRecord } from "../types";

type TaskTab = "all" | "running" | "completed" | "failed";

interface TaskRow {
  session: SessionDetail;
  workerDispatches: WorkerDispatchRecord[];
  isBackgroundChild: boolean;
  parentSessionId: string;
}

const router = useRouter();

const loading = ref(false);
const error = ref("");
const activeTab = ref<TaskTab>("all");
const search = ref("");
const rows = ref<TaskRow[]>([]);

const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase();
  return rows.value.filter((row) => {
    if (activeTab.value === "running" && !["running", "waiting_approval"].includes(row.session.status)) {
      return false;
    }
    if (activeTab.value === "completed" && row.session.status !== "completed") {
      return false;
    }
    if (activeTab.value === "failed" && row.session.status !== "failed") {
      return false;
    }
    if (!query) {
      return true;
    }
    return [
      row.session.id,
      row.session.title,
      row.session.mode_key,
      row.session.selected_agent || "",
      row.parentSessionId,
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
});

const tabs = computed(() => {
  const all = rows.value.length;
  const running = rows.value.filter((row) =>
    ["running", "waiting_approval"].includes(row.session.status),
  ).length;
  const completed = rows.value.filter((row) => row.session.status === "completed").length;
  const failed = rows.value.filter((row) => row.session.status === "failed").length;
  return [
    { id: "all" as TaskTab, label: `All (${all})` },
    { id: "running" as TaskTab, label: `Running (${running})` },
    { id: "completed" as TaskTab, label: `Completed (${completed})` },
    { id: "failed" as TaskTab, label: `Failed (${failed})` },
  ];
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

function parentSessionIdFromSession(session: SessionDetail): string {
  return String(session.metadata?.parent_session_id || "").trim();
}

function statusLabel(status: string): string {
  if (status === "waiting_approval") return "Waiting Approval";
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  if (status === "running") return "Running";
  if (status === "interrupted") return "Interrupted";
  return "Idle";
}

function modeLabel(row: TaskRow): string {
  if (row.session.mode_key === "code_review") {
    return "Code Review";
  }
  if (row.isBackgroundChild) {
    return "Background Worker";
  }
  return String(row.session.mode_key || "default");
}

function taskKind(row: TaskRow): string {
  return row.isBackgroundChild ? "Child Session" : "Parent Session";
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function workerStats(row: TaskRow): string {
  if (!row.workerDispatches.length) {
    return row.isBackgroundChild ? "No child workers" : "No worker dispatches";
  }
  const running = row.workerDispatches.filter((item) =>
    ["running", "waiting_approval"].includes(String(item.status || "").trim()),
  ).length;
  const failed = row.workerDispatches.filter((item) => String(item.status || "").trim() === "failed").length;
  const completed = row.workerDispatches.length - running - failed;
  return `${completed} completed / ${running} running / ${failed} failed`;
}

function openReport(row: TaskRow) {
  void router.push("/reports");
}

async function loadTasks() {
  loading.value = true;
  error.value = "";
  try {
    const summaries = await api.listSessions();
    const candidateSummaries = summaries
      .filter(
        (item: SessionSummary) =>
          item.mode_key === "code_review" || item.session_mode === "background_task",
      )
      .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
      .slice(0, 24);

    const details = await Promise.all(
      candidateSummaries.map((item) => api.getSession(item.id)),
    );

    rows.value = details.map((session) => {
      const parentSessionId = parentSessionIdFromSession(session);
      return {
        session,
        workerDispatches: workerDispatchesFromSession(session),
        isBackgroundChild: session.session_mode === "background_task",
        parentSessionId,
      };
    });
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "Failed to load tasks.";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadTasks();
});
</script>

<template>
  <section class="view-page task-page">
    <header class="page-head">
      <div class="head-content">
        <h2>Task Pool</h2>
        <p class="head-desc">
          Real background sessions and code review runs from the current workspace.
        </p>
      </div>
      <div class="head-actions">
        <div class="search-box">
          <i class="fa-solid fa-search"></i>
          <input v-model="search" type="text" placeholder="Search by session, title, mode..." />
        </div>
        <button class="primary-btn" :disabled="loading" @click="loadTasks">
          <i class="fa-solid fa-rotate-right"></i>
          Refresh
        </button>
      </div>
    </header>

    <div v-if="error" class="empty-state error-state">
      <strong>Failed to load task pool.</strong>
      <p>{{ error }}</p>
    </div>

    <div v-else class="task-layout">
      <div class="task-toolbar">
        <div class="task-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="tab-btn"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="task-filters">
          <span class="filter-pill">Latest {{ rows.length }} sessions</span>
          <span class="filter-pill">Mode: code_review + background_task</span>
        </div>
      </div>

      <div v-if="loading && !rows.length" class="empty-state table-empty">
        <strong>Loading task sessions...</strong>
        <p>The dashboard is syncing recent task sessions.</p>
      </div>

      <div v-else-if="!filteredRows.length" class="empty-state table-empty">
        <strong>No matching tasks.</strong>
        <p>Try another filter or start a code review task first.</p>
      </div>

      <div v-else class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-id">Session</th>
              <th class="col-name">Title</th>
              <th class="col-type">Task Kind</th>
              <th class="col-model">Agent / Mode</th>
              <th class="col-status">Status</th>
              <th class="col-stats">Worker Stats</th>
              <th class="col-actions align-right">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in filteredRows"
              :key="row.session.id"
              :class="{
                'row-active': row.session.status === 'running' || row.session.status === 'waiting_approval',
                'row-error': row.session.status === 'failed',
              }"
            >
              <td class="col-id mono strong">
                {{ row.session.id.slice(0, 8) }}
                <div v-if="row.parentSessionId" class="sub-meta">parent={{ row.parentSessionId.slice(0, 8) }}</div>
              </td>
              <td class="col-name">
                <div class="strong">{{ row.session.title }}</div>
                <div class="sub-meta">{{ formatDateTime(row.session.updated_at) }}</div>
              </td>
              <td class="col-type">
                <span class="badge badge-gray">{{ taskKind(row) }}</span>
              </td>
              <td class="col-model">
                <div class="mono">{{ row.session.selected_agent || "-" }}</div>
                <div class="sub-meta">{{ modeLabel(row) }}</div>
              </td>
              <td class="col-status">
                <span class="status-indicator" :class="`status-${row.session.status}`">
                  <span v-if="row.session.status === 'running' || row.session.status === 'waiting_approval'" class="pulse-dot"></span>
                  <i
                    v-else
                    class="fa-solid"
                    :class="row.session.status === 'completed' ? 'fa-check' : row.session.status === 'failed' ? 'fa-xmark' : 'fa-clock'"
                  ></i>
                  {{ statusLabel(row.session.status) }}
                </span>
              </td>
              <td class="col-stats">
                <div>{{ workerStats(row) }}</div>
                <div class="sub-meta">{{ row.workerDispatches.length }} dispatch records</div>
              </td>
              <td class="col-actions align-right">
                <button class="action-btn" title="Open reports" @click="openReport(row)">
                  <i class="fa-solid fa-arrow-up-right-from-square"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.task-page {
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

.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-box i {
  position: absolute;
  left: 12px;
  color: var(--muted);
  font-size: 14px;
}

.search-box input {
  height: 36px;
  padding: 0 16px 0 36px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
  width: 280px;
}

.task-layout {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}

.task-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-soft);
}

.task-tabs {
  display: flex;
  gap: 4px;
  background: var(--surface-muted);
  padding: 4px;
  border-radius: 8px;
}

.tab-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  border-radius: 6px;
  cursor: pointer;
}

.tab-btn.active {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.task-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
}

.table-container {
  flex: 1;
  overflow: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.data-table th {
  position: sticky;
  top: 0;
  background: var(--surface);
  padding: 14px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  z-index: 10;
}

.data-table td {
  padding: 16px;
  font-size: 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  vertical-align: middle;
}

.data-table tbody tr:hover {
  background: var(--surface-soft);
}

.data-table tbody tr.row-active {
  background: rgba(59, 130, 246, 0.02);
}

.data-table tbody tr.row-error {
  background: rgba(239, 68, 68, 0.02);
}

.col-id {
  width: 140px;
}

.col-name {
  min-width: 280px;
}

.col-type,
.col-model,
.col-status,
.col-stats {
  width: 180px;
}

.col-actions {
  width: 80px;
}

.align-right {
  text-align: right;
}

.mono {
  font-family: var(--font-mono, monospace);
}

.strong {
  font-weight: 600;
}

.sub-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
}

.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.badge-gray {
  background: var(--surface-muted);
  color: var(--muted);
  border: 1px solid var(--border);
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.status-running,
.status-waiting_approval {
  color: #2563eb;
}

.status-completed {
  color: #16a34a;
}

.status-failed {
  color: #dc2626;
}

.status-idle,
.status-interrupted {
  color: #6b7280;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  position: relative;
}

.pulse-dot::after {
  content: "";
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid #3b82f6;
  animation: pulse 1.5s infinite cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
}

@keyframes pulse {
  0% {
    transform: scale(0.5);
    opacity: 1;
  }
  100% {
    transform: scale(1.5);
    opacity: 0;
  }
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.action-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
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
  margin: 8px;
}

.table-empty {
  margin: 20px;
}

.error-state {
  color: #dc2626;
}

@media (max-width: 960px) {
  .page-head,
  .task-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .search-box input {
    width: 100%;
  }
}
</style>
