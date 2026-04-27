<script setup lang="ts">
import { computed } from "vue";

import type { ToolApprovalRequest } from "../../types";
import { useSessionStore } from "../../stores/session";
import { formatServerTime } from "../../utils/datetime";

const sessionStore = useSessionStore();

const pendingApprovals = computed(() => sessionStore.pendingApprovals);
const primaryApproval = computed(() => pendingApprovals.value[0] ?? null);
const pendingCount = computed(() => pendingApprovals.value.length);

function readArguments(metadata: Record<string, unknown>) {
  const argumentsPayload = metadata.arguments;
  if (!argumentsPayload || typeof argumentsPayload !== "object" || Array.isArray(argumentsPayload)) {
    return {};
  }
  return argumentsPayload as Record<string, unknown>;
}

function formatAgentLabel(value: unknown) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "Coordinator";
  }

  return normalized
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function approvalKindLabel(approval: ToolApprovalRequest) {
  switch (approval.tool_key) {
    case "cli-executor":
      return "终端命令";
    case "browser-automation":
    case "browser-control":
    case "dom-inspector":
      return "浏览器操作";
    case "api-caller":
    case "api-tester":
      return "接口请求";
    case "send-email":
    case "message-dispatch":
      return "消息发送";
    case "filesystem":
    case "file-artifact-manager":
      return "文件访问";
    default:
      return approval.tool_name || approval.tool_key;
  }
}

function approvalMetaLine(approval: ToolApprovalRequest) {
  const agentLabel = formatAgentLabel(approval.metadata?.selected_agent_key);
  const timeLabel = formatServerTime(approval.created_at);
  return `${agentLabel} · ${timeLabel}`;
}

function approvalPreviewSource(approval: ToolApprovalRequest) {
  const args = readArguments(approval.metadata);
  const lines: string[] = [];

  const pushTextLines = (value: unknown) => {
    if (typeof value !== "string") {
      return;
    }
    for (const line of value.split(/\r?\n/)) {
      const normalized = line.trim();
      if (normalized) {
        lines.push(normalized);
      }
    }
  };

  pushTextLines(args.command);

  if (lines.length === 0 && Array.isArray(args.commands)) {
    for (const item of args.commands) {
      pushTextLines(item);
    }
  }

  if (lines.length === 0 && typeof args.subject === "string") {
    lines.push(`主题：${args.subject}`);
  }

  if (lines.length === 0 && typeof args.url === "string") {
    lines.push(`访问 ${args.url}`);
  }

  if (lines.length === 0 && typeof args.target_url === "string") {
    lines.push(`访问 ${args.target_url}`);
  }

  if (lines.length === 0 && typeof args.path === "string") {
    lines.push(`路径：${args.path}`);
  }

  if (lines.length === 0 && typeof args.query === "string") {
    lines.push(`查询：${args.query}`);
  }

  if (lines.length === 0 && Array.isArray(args.to) && args.to.length > 0) {
    lines.push(`收件人：${args.to.join(", ")}`);
  }

  if (lines.length === 0) {
    lines.push(approvalKindLabel(approval));
  }

  return lines;
}

function approvalPreviewLines(approval: ToolApprovalRequest) {
  return approvalPreviewSource(approval).slice(0, 3);
}

function approvalPreviewOverflowCount(approval: ToolApprovalRequest) {
  return Math.max(0, approvalPreviewSource(approval).length - 3);
}

function approvalHint(approval: ToolApprovalRequest) {
  switch (approval.tool_key) {
    case "cli-executor":
      return "需要调用本地终端，请确认命令来源和执行范围。";
    case "browser-automation":
    case "browser-control":
    case "dom-inspector":
      return "需要驱动浏览器执行动作，请确认目标页面和操作内容。";
    case "api-caller":
    case "api-tester":
      return "需要向外部接口发起请求，请确认地址、方法和参数。";
    case "send-email":
    case "message-dispatch":
      return "需要发送外部消息，请确认收件人和内容。";
    case "filesystem":
    case "file-artifact-manager":
      return "需要访问文件系统，请确认路径和预期输出。";
    default:
      return "当前操作需要额外授权，建议确认参数后再继续。";
  }
}

async function handleDecision(approvalId: string, decision: "approved" | "denied") {
  const reason =
    decision === "approved"
      ? "用户在工作台右侧审批卡片中批准了本次执行。"
      : "用户在工作台右侧审批卡片中拒绝了本次执行。";
  await sessionStore.resolveApproval(approvalId, decision, reason);
}
</script>

<template>
  <section v-if="primaryApproval" class="approval-panel">
    <article class="approval-sidecard">
      <div class="approval-sidecard-top">
        <span class="approval-sidecard-code">AUTH</span>
        <span class="approval-sidecard-dot"></span>
      </div>

      <div class="approval-sidecard-body">
        <div class="approval-sidecard-heading">
          <strong>权限审批</strong>
          <span class="approval-sidecard-badge">待处理</span>
        </div>
        <p class="approval-sidecard-meta">{{ approvalMetaLine(primaryApproval) }}</p>

        <div class="approval-sidecard-summary">
          <span class="approval-sidecard-label">当前操作</span>
          <strong>{{ approvalKindLabel(primaryApproval) }}</strong>
          <p>{{ primaryApproval.reason || "保护型工具需要手动确认后才能继续执行。" }}</p>
        </div>

        <div class="approval-sidecard-preview">
          <span
            v-for="line in approvalPreviewLines(primaryApproval)"
            :key="line"
            class="approval-sidecard-command"
          >
            {{ line }}
          </span>
          <span
            v-if="approvalPreviewOverflowCount(primaryApproval) > 0"
            class="approval-sidecard-more"
          >
            +{{ approvalPreviewOverflowCount(primaryApproval) }} 项更多参数
          </span>
        </div>

        <p class="approval-sidecard-hint">{{ approvalHint(primaryApproval) }}</p>

        <p v-if="pendingCount > 1" class="approval-sidecard-tail">
          另有 {{ pendingCount - 1 }} 项审批正在排队。
        </p>
      </div>

      <div class="approval-sidecard-actions">
        <button
          class="secondary-btn"
          type="button"
          :disabled="sessionStore.isResolvingApproval(primaryApproval.id)"
          @click="handleDecision(primaryApproval.id, 'denied')"
        >
          拒绝
        </button>
        <button
          class="primary-btn"
          type="button"
          :disabled="sessionStore.isResolvingApproval(primaryApproval.id)"
          @click="handleDecision(primaryApproval.id, 'approved')"
        >
          <i
            v-if="sessionStore.isResolvingApproval(primaryApproval.id)"
            class="fa-solid fa-spinner fa-spin"
          ></i>
          批准
        </button>
      </div>
    </article>
  </section>
</template>
