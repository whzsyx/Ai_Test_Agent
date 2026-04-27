<script setup lang="ts">
import { computed, ref } from "vue";

import { api } from "../../services/api";
import { useSessionStore } from "../../stores/session";
import type { ChatMessage, SessionDetail, ToolApprovalRequest, WorkerDispatchRecord } from "../../types";

const sessionStore = useSessionStore();

const workerStats = computed(() => sessionStore.codeReviewWorkerStats);
const reportMeta = computed(() => sessionStore.codeReviewReportMeta);
const pendingCompletionWorker = computed(() => sessionStore.pendingCompletionWorkerMeta);
const debateProgress = computed(() => sessionStore.codeReviewDebateProgressMeta);

const selectedTask = ref<WorkerDispatchRecord | null>(null);
const selectedTaskSession = ref<SessionDetail | null>(null);
const isLoadingTaskDetail = ref(false);
const taskDetailError = ref("");

const workerRows = computed(() => {
  return sessionStore.workerDispatches
    .slice()
    .sort((left, right) => {
      const leftCompletion = Number(Boolean(left.is_completion_worker));
      const rightCompletion = Number(Boolean(right.is_completion_worker));
      if (leftCompletion !== rightCompletion) {
        return leftCompletion - rightCompletion;
      }
      const leftRound = Number(left.debate_round_index || 0);
      const rightRound = Number(right.debate_round_index || 0);
      return leftRound - rightRound;
    });
});

const selectedTaskRecentMessages = computed(() => {
  if (!selectedTaskSession.value) {
    return [];
  }
  return selectedTaskSession.value.messages
    .filter((message) => String(message.content || "").trim())
    .slice(-6)
    .reverse();
});

function statusTone(status: string) {
  if (status === "completed") return "success";
  if (status === "running" || status === "pending") return "running";
  if (status === "waiting_approval") return "warning";
  if (status === "failed" || status === "denied") return "danger";
  return "neutral";
}

function statusLabel(status: string) {
  if (status === "completed") return "已完成";
  if (status === "running") return "运行中";
  if (status === "waiting_approval") return "待审批";
  if (status === "pending") return "待启动";
  if (status === "failed") return "失败";
  if (status === "denied") return "已拒绝";
  return status || "未知";
}

function stageLabel(stage?: string, roundIndex = 0, totalRoundCount = 0) {
  if (stage === "independent_findings") {
    return "第1轮立论";
  }
  if (stage === "cross_review") {
    return `第${roundIndex || 2}轮攻防`;
  }
  if (stage === "summary_resolution") {
    const resolvedRound = roundIndex || totalRoundCount || 0;
    return resolvedRound ? `第${resolvedRound}轮裁决` : "总结裁决";
  }
  if (stage === "completed") {
    return "辩论完成";
  }
  return "待启动";
}

function roleLabel(item: WorkerDispatchRecord) {
  if (item.is_completion_worker) return "总结 Agent";
  if (item.dispatch_role === "debate_followup") return "攻防 Agent";
  return "立论 Agent";
}

function shortId(value: string | undefined) {
  const normalized = String(value || "").trim();
  if (!normalized) return "未分配";
  return normalized.length <= 12 ? normalized : `${normalized.slice(0, 8)}...`;
}

function formatTime(value: string | undefined) {
  const normalized = String(value || "").trim();
  if (!normalized) return "未更新";
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return normalized;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function approvalHeadline(approval: ToolApprovalRequest) {
  return `${approval.tool_name} / ${statusLabel(approval.status)}`;
}

function taskRoundLabel(item: WorkerDispatchRecord) {
  return stageLabel(item.debate_stage, item.debate_round_index || 0, item.debate_total_round_count || 0);
}

function messageRoleLabel(role: ChatMessage["role"]) {
  if (role === "assistant") return "Agent";
  if (role === "tool") return "Tool";
  if (role === "user") return "Input";
  if (role === "event") return "Event";
  return role;
}

async function openTaskDetail(item: WorkerDispatchRecord) {
  selectedTask.value = item;
  selectedTaskSession.value = null;
  taskDetailError.value = "";

  const childSessionId = String(item.child_session_id || "").trim();
  if (!childSessionId) {
    return;
  }

  isLoadingTaskDetail.value = true;
  try {
    selectedTaskSession.value = await api.getSession(childSessionId);
  } catch (error) {
    taskDetailError.value =
      error instanceof Error ? error.message : "加载审查任务详情失败。";
  } finally {
    isLoadingTaskDetail.value = false;
  }
}

function closeTaskDetail() {
  selectedTask.value = null;
  selectedTaskSession.value = null;
  taskDetailError.value = "";
  isLoadingTaskDetail.value = false;
}
</script>

<template>
  <section v-if="sessionStore.session" class="review-progress-panel">
    <div class="review-progress-head">
      <div>
        <strong>审批进程查看</strong>
        <p>聚合展示 reviewer 并行立论、多轮攻防、审批请求和总结报告的后台实时进度。</p>
      </div>
      <span class="registry-tag light">{{ sessionStore.session.mode_key }}</span>
    </div>

    <div class="review-progress-stage">
      <span class="registry-tag running">
        {{ debateProgress?.stage_label || stageLabel(debateProgress?.stage, debateProgress?.current_round_index || 0, debateProgress?.total_round_count || 0) }}
      </span>
      <span>阶段状态: {{ statusLabel(debateProgress?.status || "pending") }}</span>
      <span v-if="debateProgress?.current_round_index">
        当前轮次: {{ debateProgress.current_round_index }} / {{ debateProgress?.total_round_count || "?" }}
      </span>
      <span>最近更新: {{ formatTime(debateProgress?.updated_at) }}</span>
      <span v-if="debateProgress?.peer_review_count">参考样本: {{ debateProgress.peer_review_count }}</span>
    </div>

    <div class="review-progress-stats">
      <article class="review-progress-stat">
        <span>审查 Agent</span>
        <strong>{{ workerStats.reviewer_count }}</strong>
      </article>
      <article class="review-progress-stat">
        <span>运行中</span>
        <strong>{{ workerStats.running_count }}</strong>
      </article>
      <article class="review-progress-stat">
        <span>待审批</span>
        <strong>{{ workerStats.waiting_approval_count + sessionStore.pendingApprovals.length }}</strong>
      </article>
      <article class="review-progress-stat">
        <span>已完成</span>
        <strong>{{ workerStats.completed_count }}</strong>
      </article>
      <article class="review-progress-stat">
        <span>失败</span>
        <strong>{{ workerStats.failed_count }}</strong>
      </article>
      <article class="review-progress-stat">
        <span>报告状态</span>
        <strong>{{ statusLabel(reportMeta?.status || "pending") }}</strong>
      </article>
    </div>

    <div class="review-progress-grid">
      <section class="review-progress-card review-progress-card--tasks">
        <div class="review-progress-section-head">
          <strong>审查任务</strong>
          <span>{{ workerRows.length }} 项</span>
        </div>
        <div v-if="workerRows.length" class="review-progress-list review-progress-scroll">
          <button
            v-for="item in workerRows"
            :key="item.task_id"
            type="button"
            class="review-progress-item review-progress-item-button"
            @click="openTaskDetail(item)"
          >
            <div class="review-progress-item-head">
              <div class="review-progress-item-title">
                <strong>{{ item.description }}</strong>
                <span class="registry-tag light">{{ roleLabel(item) }}</span>
                <span v-if="item.debate_stage" class="registry-tag neutral">
                  {{ taskRoundLabel(item) }}
                </span>
              </div>
              <span class="registry-tag" :class="statusTone(item.status)">{{ statusLabel(item.status) }}</span>
            </div>
            <div class="review-progress-item-meta">
              <span>Agent: {{ item.agent_key }}</span>
              <span>Task: {{ shortId(item.task_id) }}</span>
              <span>Session: {{ shortId(item.child_session_id) }}</span>
              <span v-if="item.debate_round_index">轮次: {{ item.debate_round_index }}</span>
                <span v-if="item.source_round_index">来源轮次: {{ item.source_round_index }}</span>
                <span v-if="item.model_key">Model: {{ item.model_key }}</span>
                <span v-if="item.completed_at">完成: {{ formatTime(item.completed_at) }}</span>
                <span class="review-progress-item-action">点击查看详情</span>
              </div>
          </button>
        </div>
        <div v-else class="settings-empty">当前还没有代码审批子任务。</div>
      </section>

      <section class="review-progress-card review-progress-card--approvals">
        <div class="review-progress-section-head">
          <strong>审批请求</strong>
          <span>{{ sessionStore.pendingApprovals.length }} 条</span>
        </div>
        <div v-if="sessionStore.pendingApprovals.length" class="review-progress-list review-progress-scroll review-progress-scroll--compact">
          <article
            v-for="approval in sessionStore.pendingApprovals"
            :key="approval.id"
            class="review-progress-item"
          >
            <div class="review-progress-item-head">
              <strong>{{ approvalHeadline(approval) }}</strong>
              <span class="registry-tag warning">人工处理</span>
            </div>
            <div class="review-progress-item-meta">
              <span>Tool: {{ approval.tool_key }}</span>
              <span>创建: {{ formatTime(approval.created_at) }}</span>
            </div>
            <p class="review-progress-reason">{{ approval.reason }}</p>
          </article>
        </div>
        <div v-else class="settings-empty">当前没有待处理审批。</div>
      </section>
    </div>

    <section class="review-progress-card">
      <div class="review-progress-section-head">
        <strong>总结报告</strong>
        <span>{{ statusLabel(reportMeta?.status || "pending") }}</span>
      </div>
      <div class="review-progress-report-meta">
        <span>报告 Agent: {{ reportMeta?.agent_key || "code-review-synthesizer" }}</span>
        <span>报告会话: {{ shortId(reportMeta?.report_session_id) }}</span>
        <span>最近更新: {{ formatTime(reportMeta?.updated_at) }}</span>
        <span v-if="reportMeta?.completed_at">完成时间: {{ formatTime(reportMeta.completed_at) }}</span>
      </div>
      <p v-if="reportMeta?.description" class="review-progress-reason">{{ reportMeta.description }}</p>
      <p v-if="reportMeta?.summary" class="review-progress-reason">{{ reportMeta.summary }}</p>
      <p
        v-else-if="pendingCompletionWorker?.description && !workerStats.completion_dispatch"
        class="review-progress-reason"
      >
        总结 Agent 已排队，等待所有辩论轮次结束后自动启动：{{ pendingCompletionWorker.description }}
      </p>
      <div v-else class="settings-empty">当前还没有报告摘要。</div>
    </section>

    <teleport to="body">
      <div v-if="selectedTask" class="review-task-modal-backdrop" @click.self="closeTaskDetail">
        <section class="review-task-modal">
          <div class="review-task-modal-head">
            <div>
              <strong>{{ selectedTask.description }}</strong>
              <p>
                {{ roleLabel(selectedTask) }} · {{ taskRoundLabel(selectedTask) }} ·
                {{ statusLabel(selectedTask.status) }}
              </p>
            </div>
            <button type="button" class="review-task-close" @click="closeTaskDetail">关闭</button>
          </div>

          <div class="review-task-modal-body">
            <div class="review-task-modal-meta">
              <span>Agent: {{ selectedTask.agent_key }}</span>
              <span>Task ID: {{ selectedTask.task_id }}</span>
              <span>子会话: {{ selectedTask.child_session_id || "未创建" }}</span>
              <span v-if="selectedTask.debate_round_index">轮次: {{ selectedTask.debate_round_index }}</span>
              <span v-if="selectedTask.source_round_index">来源轮次: {{ selectedTask.source_round_index }}</span>
              <span v-if="selectedTask.model_key">Model: {{ selectedTask.model_key }}</span>
              <span v-if="selectedTask.completed_at">完成时间: {{ formatTime(selectedTask.completed_at) }}</span>
            </div>

            <div v-if="isLoadingTaskDetail" class="settings-empty">正在加载任务详情...</div>
            <div v-else-if="taskDetailError" class="review-task-error">{{ taskDetailError }}</div>
            <template v-else-if="selectedTaskSession">
              <div class="review-task-session-stats">
                <span>会话状态: {{ statusLabel(selectedTaskSession.status) }}</span>
                <span>消息数: {{ selectedTaskSession.messages.length }}</span>
                <span>事件数: {{ selectedTaskSession.event_count }}</span>
                <span>快照数: {{ selectedTaskSession.snapshot_count }}</span>
                <span>最后更新: {{ formatTime(selectedTaskSession.updated_at) }}</span>
              </div>

              <div class="review-task-message-list">
                <article
                  v-for="message in selectedTaskRecentMessages"
                  :key="message.id"
                  class="review-task-message"
                >
                  <details v-if="message.role === 'tool'" class="review-task-message-details">
                    <summary style="cursor: pointer; outline: none;">
                      <div class="review-task-message-head" style="display: inline-flex; width: calc(100% - 20px); vertical-align: top;">
                        <strong>{{ messageRoleLabel(message.role) }} <span style="font-weight: normal; font-size: 12px; color: #6b7280; margin-left: 6px;">(点击展开/收起)</span></strong>
                        <span>{{ formatTime(message.created_at) }}</span>
                      </div>
                    </summary>
                    <pre>{{ message.content }}</pre>
                  </details>
                  <template v-else>
                    <div class="review-task-message-head">
                      <strong>{{ messageRoleLabel(message.role) }}</strong>
                      <span>{{ formatTime(message.created_at) }}</span>
                    </div>
                    <pre>{{ message.content }}</pre>
                  </template>
                </article>
              </div>
            </template>
            <div v-else class="settings-empty">当前任务还没有可展开的子会话详情。</div>
          </div>
        </section>
      </div>
    </teleport>
  </section>
</template>

<style>
.review-progress-panel {
  display: grid;
  gap: 16px;
}

.review-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.review-progress-head p {
  margin: 6px 0 0;
  color: var(--text-soft, #6b7280);
  font-size: 13px;
}

.review-progress-stage {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  color: var(--text-soft, #6b7280);
  font-size: 13px;
}

.review-progress-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}

.review-progress-stat,
.review-progress-card,
.review-progress-item,
.review-task-modal {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
}

.review-progress-stat {
  padding: 14px 16px;
}

.review-progress-stat span {
  display: block;
  color: var(--text-soft, #6b7280);
  font-size: 12px;
}

.review-progress-stat strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
}

.review-progress-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.review-progress-card {
  padding: 16px;
  min-height: 0;
}

.review-progress-card--tasks,
.review-progress-card--approvals {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.review-progress-card--tasks {
  min-height: 560px;
  max-height: 560px;
}

.review-progress-card--approvals {
  min-height: 360px;
  max-height: 560px;
}

.review-progress-section-head,
.review-progress-item-head,
.review-progress-item-title,
.review-task-message-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.review-progress-section-head {
  margin-bottom: 12px;
}

.review-progress-section-head span {
  color: var(--text-soft, #6b7280);
  font-size: 12px;
}

.review-progress-list {
  display: grid;
  gap: 10px;
}

.review-progress-scroll {
  max-height: 460px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.review-progress-card--tasks .review-progress-scroll,
.review-progress-card--approvals .review-progress-scroll {
  max-height: 100%;
}

.review-progress-scroll--compact {
  max-height: 260px;
}

.review-progress-item {
  padding: 12px;
}

.review-progress-item-button {
  appearance: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
  border: 1px solid rgba(15, 23, 42, 0.08);
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.review-progress-item-button:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.24);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.review-progress-item-button:focus-visible {
  outline: 2px solid rgba(37, 99, 235, 0.32);
  outline-offset: 2px;
  border-color: rgba(37, 99, 235, 0.24);
}

.review-progress-item-title {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.review-progress-item-meta,
.review-progress-report-meta,
.review-task-modal-meta,
.review-task-session-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 8px;
  color: var(--text-soft, #6b7280);
  font-size: 12px;
}

.review-progress-item-action {
  margin-left: auto;
  color: #2563eb;
  font-weight: 600;
}

.review-progress-reason,
.review-task-message pre {
  margin: 10px 0 0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.review-task-message pre {
  margin-top: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.04);
  font-family: "Consolas", "SFMono-Regular", monospace;
  font-size: 12px;
  overflow-x: auto;
}

.registry-tag.running {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.registry-tag.success {
  background: rgba(16, 185, 129, 0.12);
  color: #059669;
}

.registry-tag.warning {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}

.registry-tag.danger {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.registry-tag.neutral {
  background: rgba(148, 163, 184, 0.14);
  color: #475569;
}

.review-task-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(6px);
}

.review-task-modal {
  width: min(920px, 100%);
  max-height: min(82vh, 840px);
  display: grid;
  grid-template-rows: auto 1fr;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.24);
}

.review-task-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.review-task-modal-head p {
  margin: 6px 0 0;
  color: var(--text-soft, #6b7280);
  font-size: 13px;
}

.review-task-close {
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: #fff;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
}

.review-task-modal-body {
  padding: 18px 20px 20px;
  overflow-y: auto;
  display: grid;
  gap: 14px;
}

.review-task-message-list {
  display: grid;
  gap: 12px;
}

.review-task-message {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(248, 250, 252, 0.88);
}

.review-task-error {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
  line-height: 1.6;
}

@media (max-width: 1100px) {
  .review-progress-grid {
    grid-template-columns: 1fr;
  }
}
</style>
