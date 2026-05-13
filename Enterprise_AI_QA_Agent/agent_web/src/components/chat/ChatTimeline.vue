<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { t } from "../../services/i18n";
import type { ChatMessage, InputAttachment } from "../../types";
import { formatServerDateTime } from "../../utils/datetime";

const props = defineProps<{
  messages: ChatMessage[];
}>();

const visibleMessages = computed(() =>
  props.messages.filter(
    (message) =>
      !(
        message.role === "assistant" &&
        isStreamingAssistant(message) &&
        !String(message.content || "").trim()
      ),
  ),
);

const historyRef = ref<HTMLElement | null>(null);
const endRef = ref<HTMLElement | null>(null);
const scrollContainerRef = ref<HTMLElement | null>(null);
const BOUNDARY_RESUME_THRESHOLD = 150;
let resizeObserver: ResizeObserver | null = null;
let suppressScrollSync = false;
let releaseScrollSyncFrame = 0;
const userOverrideActive = ref(false);

const messageRenderSignature = computed(() =>
  visibleMessages.value
    .map((message) => {
      const deliveryStatus = String(message.metadata?.delivery_status || "").trim();
      return `${message.id}:${message.content.length}:${deliveryStatus}`;
    })
    .join("|"),
);
const streamingSignature = computed(() =>
  visibleMessages.value
    .filter((message) => isStreamingAssistant(message))
    .map((message) => `${message.id}:${message.content.length}`)
    .join("|"),
);
const hasStreamingAssistantOutput = computed(() => streamingSignature.value.length > 0);

function getComposerBoundaryTop() {
  const composer = document.querySelector(".home-composer") as HTMLElement | null;
  if (!composer) {
    return null;
  }
  // Added 60px to push the boundary line downwards
  return composer.getBoundingClientRect().top + 28; 
}

function getTailDistanceToBoundary() {
  const boundaryTop = getComposerBoundaryTop();
  const tail = endRef.value;
  if (boundaryTop === null || !tail) {
    return null;
  }
  return tail.getBoundingClientRect().bottom - boundaryTop;
}

function isAtBottom() {
  const container = scrollContainerRef.value;
  if (!container) {
    return true;
  }
  // User is considered at bottom if they are within the threshold
  return container.scrollHeight - Math.ceil(container.scrollTop) - container.clientHeight <= BOUNDARY_RESUME_THRESHOLD;
}

function withProgrammaticScroll(callback: () => void) {
  suppressScrollSync = true;
  callback();
  if (releaseScrollSyncFrame) {
    cancelAnimationFrame(releaseScrollSyncFrame);
  }
  releaseScrollSyncFrame = window.requestAnimationFrame(() => {
    suppressScrollSync = false;
    releaseScrollSyncFrame = 0;
  });
}

function handleScroll() {
  if (suppressScrollSync) {
    return;
  }
  if (!hasStreamingAssistantOutput.value) {
    userOverrideActive.value = false;
    return;
  }
  const overflow = getTailDistanceToBoundary();
  if (overflow === null) {
    userOverrideActive.value = !isAtBottom();
  } else {
    // If the tail is higher than the composer top, user is not at the bottom visual boundary
    // But if it overflows the composer top, and we are not forcing scroll, 
    // it means user has scrolled up
    userOverrideActive.value = overflow < -BOUNDARY_RESUME_THRESHOLD || !isAtBottom();
  }
}

function handleWheel(event: WheelEvent) {
  if (event.deltaY !== 0 && hasStreamingAssistantOutput.value) {
    userOverrideActive.value = true;
  }
}

function handleTouchMove() {
  if (hasStreamingAssistantOutput.value) {
    userOverrideActive.value = true;
  }
}

async function scrollToBoundary(force = false) {
  await nextTick();
  const container = scrollContainerRef.value;
  if (!container) {
    return;
  }
  if (!force && !hasStreamingAssistantOutput.value) {
    return;
  }
  if (!force && userOverrideActive.value) {
    return;
  }

  const overflow = getTailDistanceToBoundary();
  // If the content isn't long enough to hit the composer, or we don't know the composer pos
  if (overflow === null || overflow <= 0) {
    if (force) {
      withProgrammaticScroll(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: "auto",
        });
      });
    }
    return;
  }

  withProgrammaticScroll(() => {
    // Just scroll down by the exact overflow amount so the tail sits perfectly above the composer
    container.scrollTo({
      top: container.scrollTop + overflow,
      behavior: "auto",
    });
  });
}

onMounted(() => {
  scrollContainerRef.value = historyRef.value?.closest(".prototype-content") as HTMLElement | null;
  scrollContainerRef.value?.addEventListener("scroll", handleScroll, { passive: true });
  scrollContainerRef.value?.addEventListener("wheel", handleWheel, { passive: true });
  scrollContainerRef.value?.addEventListener("touchmove", handleTouchMove, { passive: true });
  resizeObserver = new ResizeObserver(() => {
    if (hasStreamingAssistantOutput.value) {
      void scrollToBoundary();
    }
  });
  if (historyRef.value) {
    resizeObserver.observe(historyRef.value);
  }
  void scrollToBoundary(true);
});

onBeforeUnmount(() => {
  scrollContainerRef.value?.removeEventListener("scroll", handleScroll);
  scrollContainerRef.value?.removeEventListener("wheel", handleWheel);
  scrollContainerRef.value?.removeEventListener("touchmove", handleTouchMove);
  resizeObserver?.disconnect();
  resizeObserver = null;
  if (releaseScrollSyncFrame) {
    cancelAnimationFrame(releaseScrollSyncFrame);
    releaseScrollSyncFrame = 0;
  }
});

watch(
  () => visibleMessages.value.length,
  (newLength, oldLength) => {
    if (newLength > oldLength) {
      userOverrideActive.value = false;
      void scrollToBoundary(true);
    }
  }
);

watch(messageRenderSignature, (_, previousValue) => {
  if (!previousValue) {
    userOverrideActive.value = false;
    void scrollToBoundary(true);
  }
});

watch(streamingSignature, () => {
  if (!hasStreamingAssistantOutput.value) {
    userOverrideActive.value = false;
    return;
  }
  void scrollToBoundary();
});

function messageKind(message: ChatMessage) {
  return String(message.metadata?.message_kind || "").trim();
}

function labelForMessage(message: ChatMessage) {
  const kind = messageKind(message);
  if (kind === "task_notification") return t("chat.worker_notification");
  if (kind === "coordinator_assignment") return t("chat.worker_assignment");
  const role = message.role;
  if (role === "user") return t("chat.user_prompt");
  if (role === "assistant") return t("chat.agent_response");
  if (role === "tool") return t("chat.tool_output");
  if (role === "system") return t("chat.system");
  return t("chat.event");
}

function attachmentsForMessage(message: ChatMessage): InputAttachment[] {
  const attachments = message.metadata?.attachments;
  if (!Array.isArray(attachments)) {
    return [];
  }
  return attachments.filter(
    (item): item is InputAttachment =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as InputAttachment).name === "string",
  );
}

function formatAttachmentSize(value: unknown) {
  const size = Number(value || 0);
  if (!Number.isFinite(size) || size <= 0) {
    return "";
  }
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
}

function localizedAttachmentSecondaryText(attachment: InputAttachment) {
  const formatLabel = String(attachment.metadata?.format_label || t("chat.session_attachment"));
  const sizeLabel = formatAttachmentSize(attachment.metadata?.size_bytes);
  return sizeLabel ? `${formatLabel} 路 ${sizeLabel}` : formatLabel;
}

function localizedDeliveryLabel(message: ChatMessage) {
  const deliveryStatus = String(message.metadata?.delivery_status || "").trim();
  if (deliveryStatus === "pending") return t("chat.sending_status");
  if (deliveryStatus === "streaming") return t("chat.streaming_status");
  if (deliveryStatus === "failed") return t("chat.failed_status");
  return "";
}

function attachmentSecondaryText(attachment: InputAttachment) {
  const formatLabel = String(attachment.metadata?.format_label || "会话附件");
  const sizeLabel = formatAttachmentSize(attachment.metadata?.size_bytes);
  return sizeLabel ? `${formatLabel} · ${sizeLabel}` : formatLabel;
}

function deliveryLabel(message: ChatMessage) {
  const deliveryStatus = String(message.metadata?.delivery_status || "").trim();
  if (deliveryStatus === "pending") return "发送中...";
  if (deliveryStatus === "streaming") return "生成中...";
  if (deliveryStatus === "failed") return "发送失败";
  return "";
}

function isStreamingAssistant(message: ChatMessage) {
  return message.role === "assistant" && String(message.metadata?.delivery_status || "").trim() === "streaming";
}

function toolSummary(content: string) {
  try {
    const parsed = JSON.parse(content) as { summary?: string; status?: string };
    const summary = String(parsed.summary || "").trim();
    const status = String(parsed.status || "").trim();
    if (summary && status) return `${status}: ${summary}`;
    if (summary) return summary;
    if (status) return `status: ${status}`;
  } catch {
    return content.split("\n")[0]?.trim() || "Expand to view tool output";
  }
  return "Expand to view tool output";
}

function localizedToolSummary(content: string) {
  const summary = toolSummary(content);
  return summary === "Expand to view tool output" ? t("chat.expand_tool_output") : summary;
}

function decodeUnicodeEscapes(content: string) {
  return String(content || "").replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) =>
    String.fromCharCode(Number.parseInt(hex, 16)),
  );
}

function normalizeEmbeddedObservationContent(content: string) {
  return decodeUnicodeEscapes(content)
    .split("\n")
    .map((line) => {
      const separatorIndex = line.indexOf("=");
      if (separatorIndex <= 0) {
        return line;
      }
      const key = line.slice(0, separatorIndex);
      const rawValue = line.slice(separatorIndex + 1).trim();
      if (!["output", "context"].includes(key)) {
        return `${key}=${rawValue}`;
      }
      try {
        const parsed = JSON.parse(rawValue) as unknown;
        return `${key}=${JSON.stringify(normalizeToolDisplayValue(parsed), null, 2)}`;
      } catch {
        return `${key}=${rawValue}`;
      }
    })
    .join("\n");
}

function normalizeToolDisplayValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeToolDisplayValue(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        normalizeToolDisplayValue(item),
      ]),
    );
  }
  if (typeof value === "string") {
    const decoded = decodeUnicodeEscapes(value);
    if (decoded.includes("tool_key=") && (decoded.includes("\noutput=") || decoded.includes("\ncontext="))) {
      return normalizeEmbeddedObservationContent(decoded);
    }
    return decoded;
  }
  return value;
}

function formatToolOutputContent(content: string) {
  try {
    const parsed = JSON.parse(content) as unknown;
    return JSON.stringify(normalizeToolDisplayValue(parsed), null, 2);
  } catch {
    return normalizeEmbeddedObservationContent(content);
  }
}

function isTransientToolMessage(message: ChatMessage) {
  return message.role === "tool" && message.metadata?.transient_tool_event === true;
}

function toolStatusTone(status: string) {
  if (status === "completed") return "online";
  if (status === "running" || status === "queued" || status === "waiting_approval" || status === "partial") {
    return "degraded";
  }
  if (status === "failed" || status === "denied" || status === "cancelled") return "offline";
  return "online";
}

function toolStatusLabel(status: string) {
  switch (status) {
    case "queued":
      return "排队中";
    case "running":
      return "运行中";
    case "waiting_approval":
      return "等待审批";
    case "completed":
      return "已完成";
    case "partial":
      return "部分完成";
    case "failed":
      return "失败";
    case "denied":
      return "已拒绝";
    case "cancelled":
      return "已取消";
    default:
      return status || "处理中";
  }
}

function parseToolPayload(message: ChatMessage) {
  try {
    const parsed = JSON.parse(message.content) as {
      status?: string;
      summary?: string;
      output?: Record<string, unknown>;
    };
    return {
      status: String(parsed.status || message.metadata?.status || message.metadata?.tool_progress_status || "").trim(),
      summary: String(parsed.summary || "").trim(),
      output:
        parsed.output && typeof parsed.output === "object" && !Array.isArray(parsed.output)
          ? parsed.output
          : {},
    };
  } catch {
    return {
      status: String(message.metadata?.status || message.metadata?.tool_progress_status || "").trim(),
      summary: toolSummary(message.content),
      output: {},
    };
  }
}

function toolHeadline(message: ChatMessage) {
  return String(message.metadata?.tool_name || message.metadata?.tool_key || "Tool").trim() || "Tool";
}

function toolMetaItems(message: ChatMessage) {
  const items: string[] = [];
  const toolKey = String(message.metadata?.tool_key || "").trim();
  const callId = String(message.metadata?.tool_call_id || "").trim();
  const approvalId = String(message.metadata?.approval_id || "").trim();
  if (toolKey) {
    items.push(toolKey);
  }
  if (callId) {
    items.push(`call ${callId.slice(0, 8)}`);
  }
  if (approvalId) {
    items.push(`approval ${approvalId.slice(0, 8)}`);
  }
  return items;
}

function displayAssistantContent(content: string) {
  const marker = content.indexOf("[Framework]");
  return marker >= 0 ? content.slice(0, marker).trim() : content.trim();
}

function renderAssistantMarkdown(content: string) {
  const source = displayAssistantContent(content);
  const normalized = source.replace(/\r\n/g, "\n");
  const codeBlocks: string[] = [];
  const withPlaceholders = normalized.replace(/```([\w-]*)\n?([\s\S]*?)```/g, (_, language = "", body = "") => {
    const token = `__CODE_BLOCK_${codeBlocks.length}__`;
    const escapedBody = escapeHtml(String(body).trimEnd());
    const className = language ? ` class="language-${escapeHtml(String(language))}"` : "";
    codeBlocks.push(`<pre class="assistant-code-block"><code${className}>${escapedBody}</code></pre>`);
    return token;
  });

  const lines = withPlaceholders.split("\n");
  const blocks: string[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listKind: "ul" | "ol" | null = null;
  let tableRows: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length || !listKind) return;
    blocks.push(`<${listKind}>${listItems.join("")}</${listKind}>`);
    listItems = [];
    listKind = null;
  };

  const flushTable = () => {
    if (!tableRows.length) return;
    blocks.push(renderMarkdownTable(tableRows));
    tableRows = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      flushTable();
      continue;
    }

    if (line.startsWith("__CODE_BLOCK_") && line.endsWith("__")) {
      flushParagraph();
      flushList();
      flushTable();
      blocks.push(line);
      continue;
    }

    if (isMarkdownTableRow(line)) {
      flushParagraph();
      flushList();
      tableRows.push(line);
      continue;
    }

    const horizontalRule = line.match(/^(-{3,}|\*{3,}|_{3,})$/);
    if (horizontalRule) {
      flushParagraph();
      flushList();
      flushTable();
      blocks.push("<hr>");
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      flushList();
      flushTable();
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.*)$/);
    if (ordered) {
      flushParagraph();
      flushTable();
      if (listKind && listKind !== "ol") flushList();
      listKind = "ol";
      listItems.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
      continue;
    }

    const bullet = line.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      flushParagraph();
      flushTable();
      if (listKind && listKind !== "ul") flushList();
      listKind = "ul";
      listItems.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      continue;
    }

    if (listKind) flushList();
    if (tableRows.length) flushTable();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  flushTable();

  return blocks
    .join("")
    .replace(/__CODE_BLOCK_(\d+)__/g, (_, index) => codeBlocks[Number(index)] || "");
}

function isMarkdownTableRow(line: string) {
  return line.startsWith("|") && line.endsWith("|") && line.split("|").length >= 4;
}

function isMarkdownTableSeparator(line: string) {
  const cells = splitMarkdownTableCells(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s/g, "")));
}

function splitMarkdownTableCells(line: string) {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderMarkdownTable(rows: string[]) {
  if (rows.length < 2 || !isMarkdownTableSeparator(rows[1])) {
    return `<p>${rows.map((row) => renderInlineMarkdown(row)).join("<br>")}</p>`;
  }

  const headers = splitMarkdownTableCells(rows[0]);
  const bodyRows = rows.slice(2).filter((row) => !isMarkdownTableSeparator(row));
  const headHtml = headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("");
  const bodyHtml = bodyRows
    .map((row) => {
      const cells = splitMarkdownTableCells(row);
      return `<tr>${cells.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`;
    })
    .join("");

  return `<div class="assistant-table-shell"><table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
}

function renderInlineMarkdown(content: string) {
  const inlineCodes: string[] = [];
  let html = escapeHtml(content).replace(/`([^`]+)`/g, (_, code) => {
    const token = `@@IC${inlineCodes.length}@@`;
    inlineCodes.push(`<code>${escapeHtml(String(code))}</code>`);
    return token;
  });

  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");
  html = html.replace(/_(.+?)_/g, "<em>$1</em>");

  return html.replace(/@@IC(\d+)@@/g, (_, index) => inlineCodes[Number(index)] || "");
}

function escapeHtml(content: string) {
  return content
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
</script>

<template>
  <div ref="historyRef" class="home-history" v-if="visibleMessages.length">
    <article
      v-for="message in visibleMessages"
      :key="message.id"
      class="conversation-entry"
      :class="`conversation-entry-${message.role}`"
    >
      <div class="conversation-entry-meta">
        <span>{{ labelForMessage(message) }}</span>
        <span>
          {{ formatServerDateTime(message.created_at) }}
          <template v-if="localizedDeliveryLabel(message)">
            - {{ localizedDeliveryLabel(message) }}
          </template>
        </span>
      </div>
      <div v-if="message.role === 'tool' && isTransientToolMessage(message)" class="tool-progress-card">
        <div class="tool-progress-head">
          <div class="tool-progress-title">
            <span
              :class="[
                'runtime-status-square-dot',
                `is-${toolStatusTone(parseToolPayload(message).status)}`,
                { 'is-pulsing': parseToolPayload(message).status === 'running' },
              ]"
            ></span>
            <strong>{{ toolHeadline(message) }}</strong>
          </div>
          <span class="tool-progress-status">
            {{ toolStatusLabel(parseToolPayload(message).status) }}
          </span>
        </div>
        <p class="tool-progress-summary">
          {{ parseToolPayload(message).summary || "Tool is processing the current step." }}
        </p>
        <div v-if="toolMetaItems(message).length" class="tool-progress-meta">
          <span v-for="item in toolMetaItems(message)" :key="item" class="tool-progress-chip">{{ item }}</span>
        </div>
      </div>
      <details v-else-if="message.role === 'tool'" class="tool-output-details">
        <summary class="tool-output-summary">
          <span>{{ localizedToolSummary(message.content) }}</span>
          <span class="tool-output-hint">
            <span class="tool-output-hint-collapsed">展开</span>
            <span class="tool-output-hint-expanded">收起</span>
          </span>
        </summary>
        <pre class="conversation-entry-content tool-output-content">{{ formatToolOutputContent(message.content) }}</pre>
      </details>
      <div
        v-else-if="message.role === 'assistant'"
        :class="[
          'conversation-entry-content',
          'conversation-entry-markdown',
          { 'conversation-entry-streaming': isStreamingAssistant(message) },
        ]"
        v-html="renderAssistantMarkdown(message.content)"
      />
      <div v-else class="conversation-entry-stack">
        <div v-if="attachmentsForMessage(message).length" class="conversation-entry-attachments">
          <div
            v-for="(attachment, index) in attachmentsForMessage(message)"
            :key="`${message.id}-${attachment.uri || attachment.name}-${index}`"
            class="conversation-entry-attachment"
          >
            <div class="conversation-entry-attachment-icon">
              <i class="fa-solid fa-file-lines"></i>
            </div>
            <div class="conversation-entry-attachment-copy">
              <strong>{{ attachment.name }}</strong>
              <span>{{ localizedAttachmentSecondaryText(attachment) }}</span>
            </div>
          </div>
        </div>
        <pre class="conversation-entry-content">{{ message.content }}</pre>
      </div>
    </article>
    <div ref="endRef" class="conversation-end-sentinel" aria-hidden="true"></div>
  </div>
</template>

<style scoped>
.conversation-entry-stack {
  display: grid;
  gap: 10px;
}

.conversation-entry-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.conversation-entry-attachment {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 220px;
  max-width: min(360px, 100%);
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.92);
}

.conversation-entry-attachment-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
  flex-shrink: 0;
}

.conversation-entry-attachment-copy {
  min-width: 0;
}

.conversation-entry-attachment-copy strong,
.conversation-entry-attachment-copy span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-entry-attachment-copy strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.conversation-entry-attachment-copy span {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
}
</style>
