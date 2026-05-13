<script setup lang="ts">
import { computed } from "vue";

import { t } from "../../services/i18n";
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
      return t("approvalPanel.kind_cli");
    case "browser-automation":
    case "browser-control":
    case "dom-inspector":
      return t("approvalPanel.kind_browser");
    case "api-caller":
    case "api-tester":
      return t("approvalPanel.kind_api");
    case "send-email":
    case "message-dispatch":
      return t("approvalPanel.kind_message");
    case "filesystem":
    case "file-artifact-manager":
      return t("approvalPanel.kind_file");
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
    lines.push(`${t("approvalPanel.subject")}${args.subject}`);
  }

  if (lines.length === 0 && typeof args.url === "string") {
    lines.push(`${t("approvalPanel.visit")} ${args.url}`);
  }

  if (lines.length === 0 && typeof args.target_url === "string") {
    lines.push(`${t("approvalPanel.visit")} ${args.target_url}`);
  }

  if (lines.length === 0 && typeof args.path === "string") {
    lines.push(`${t("approvalPanel.path")}${args.path}`);
  }

  if (lines.length === 0 && typeof args.query === "string") {
    lines.push(`${t("approvalPanel.query")}${args.query}`);
  }

  if (lines.length === 0 && Array.isArray(args.to) && args.to.length > 0) {
    lines.push(`${t("approvalPanel.recipients")}${args.to.join(", ")}`);
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
      return t("approvalPanel.hint_cli");
    case "browser-automation":
    case "browser-control":
    case "dom-inspector":
      return t("approvalPanel.hint_browser");
    case "api-caller":
    case "api-tester":
      return t("approvalPanel.hint_api");
    case "send-email":
    case "message-dispatch":
      return t("approvalPanel.hint_message");
    case "filesystem":
    case "file-artifact-manager":
      return t("approvalPanel.hint_file");
    default:
      return t("approvalPanel.hint_default");
  }
}

async function handleDecision(approvalId: string, decision: "approved" | "denied") {
  const reason =
    decision === "approved"
      ? t("approvalPanel.reason_approved")
      : t("approvalPanel.reason_denied");
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
          <strong>{{ t("approvalPanel.title") }}</strong>
          <span class="approval-sidecard-badge">{{ t("approvalPanel.pending") }}</span>
        </div>
        <p class="approval-sidecard-meta">{{ approvalMetaLine(primaryApproval) }}</p>

        <div class="approval-sidecard-summary">
          <span class="approval-sidecard-label">{{ t("approvalPanel.current_action") }}</span>
          <strong>{{ approvalKindLabel(primaryApproval) }}</strong>
          <p>{{ primaryApproval.reason || t("approvalPanel.default_reason") }}</p>
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
            +{{ approvalPreviewOverflowCount(primaryApproval) }} {{ t("approvalPanel.more_params") }}
          </span>
        </div>

        <p class="approval-sidecard-hint">{{ approvalHint(primaryApproval) }}</p>

        <p v-if="pendingCount > 1" class="approval-sidecard-tail">
          {{ t("approvalPanel.queue_hint", { count: String(pendingCount - 1) }) }}
        </p>
      </div>

      <div class="approval-sidecard-actions">
        <button
          class="secondary-btn"
          type="button"
          :disabled="sessionStore.isResolvingApproval(primaryApproval.id)"
          @click="handleDecision(primaryApproval.id, 'denied')"
        >
          {{ t("approvalPanel.deny") }}
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
          {{ t("approvalPanel.approve") }}
        </button>
      </div>
    </article>
  </section>
</template>
