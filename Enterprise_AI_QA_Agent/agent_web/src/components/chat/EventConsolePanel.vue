<script setup lang="ts">
import { computed, ref } from "vue";

import { t } from "../../services/i18n";
import type { ExecutionEvent, PendingInputQueueEntry } from "../../types";
import { useSessionStore } from "../../stores/session";
import { formatServerTime } from "../../utils/datetime";

const sessionStore = useSessionStore();
const eventsExpanded = ref(false);

const timeline = computed(() => {
  if (sessionStore.replayTimeline.length > 0) {
    return sessionStore.replayTimeline.slice(0, 16);
  }
  return sessionStore.activity.slice(0, 16);
});

const queueEntries = computed(() => sessionStore.pendingInputQueue.slice(0, 6));

const transcriptStats = computed(() => {
  const summary = sessionStore.transcriptSummary;
  return [
    { key: "conversation", label: t("eventConsole.conversation_messages"), value: summary.conversation_count, tone: "neutral" },
    { key: "tool", label: t("eventConsole.tool_messages"), value: summary.tool_count, tone: "tool" },
    { key: "error", label: t("eventConsole.error_messages"), value: summary.error_count, tone: "error" },
    { key: "eligible", label: t("eventConsole.context_eligible"), value: summary.context_eligible_count, tone: "success" },
    { key: "queue", label: t("eventConsole.queued_turns"), value: sessionStore.queuedTurnCount, tone: "queue" },
  ];
});

const transcriptEntries = computed(() => sessionStore.recentTranscriptEntries.slice(0, 6));

function previewText(value: string, limit = 96) {
  const normalized = String(value || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "";
  }
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, limit - 3))}...`;
}

function queueBehaviorLabel(value: string) {
  if (value === "interrupt_then_retry") return t("eventConsole.behavior_interrupt_retry");
  if (value === "enqueue_if_busy") return t("eventConsole.behavior_enqueue");
  if (value === "reject_when_busy") return t("eventConsole.behavior_reject");
  return value || t("eventConsole.behavior_enqueue");
}

function statusLabel(value: string) {
  if (!value) return t("eventConsole.status_pending");
  const normalized = value.replace(/_/g, " ");
  const mapping: Record<string, string> = {
    running: t("eventConsole.status_running"),
    "waiting approval": t("eventConsole.status_waiting_approval"),
    interrupted: t("eventConsole.status_interrupted"),
    completed: t("eventConsole.status_completed"),
    failed: t("eventConsole.status_failed"),
    idle: t("eventConsole.status_idle"),
    busy: t("eventConsole.status_busy"),
    "interrupt active turn": t("eventConsole.status_interrupt_turn"),
    "wait for active turn": t("eventConsole.status_wait_turn"),
  };
  return mapping[normalized] || normalized;
}

function eventMessage(event: ExecutionEvent) {
  const payload = event.payload ?? {};

  if (event.type === "input.queued") {
    const queuedTurnId = String(payload.queued_turn_id || "").trim();
    const busyStatus = statusLabel(String(payload.busy_status || "busy").trim());
    const queueDepth = String(payload.queue_depth || "0").trim();
    const queueBehavior = queueBehaviorLabel(String(payload.queue_behavior || "enqueue_if_busy").trim());
    return t("eventConsole.msg_queued", { turnId: queuedTurnId || t("eventConsole.unassigned"), status: busyStatus, depth: queueDepth, behavior: queueBehavior });
  }

  if (event.type === "input.dequeued") {
    const queueEntryId = String(payload.queue_entry_id || "").trim();
    const remaining = String(payload.remaining_queue_depth || "0").trim();
    return t("eventConsole.msg_dequeued", { entryId: queueEntryId || t("eventConsole.unknown"), remaining });
  }

  if (event.type === "queue.interrupted_turn_superseded") {
    const supersededTurnId = String(payload.superseded_turn_id || "").trim();
    const nextTurnId = String(payload.next_turn_id || "").trim();
    return t("eventConsole.msg_superseded", { superseded: supersededTurnId || t("eventConsole.unknown"), next: nextTurnId || t("eventConsole.unknown") });
  }

  if (
    event.type === "runtime.interrupt_requested" &&
    String(payload.source || "").trim() === "queued_input"
  ) {
    const queueEntryId = String(payload.queue_entry_id || "").trim();
    return t("eventConsole.msg_interrupt", { entryId: queueEntryId || t("eventConsole.unknown") });
  }

  const message = payload.message;
  if (typeof message === "string" && message.trim()) {
    return message;
  }
  const summary = payload.summary;
  if (typeof summary === "string" && summary.trim()) {
    return summary;
  }
  const phase = payload.phase;
  if (typeof phase === "string" && phase.trim()) {
    return phase;
  }
  return "";
}

function bucketLabel(bucket: string) {
  if (bucket === "tool") return t("eventConsole.bucket_tool");
  if (bucket === "error") return t("eventConsole.bucket_error");
  return t("eventConsole.bucket_conversation");
}

function bucketClass(bucket: string) {
  if (bucket === "tool") return "tool";
  if (bucket === "error") return "error";
  return "conversation";
}

function roleLabel(role: string) {
  if (role === "user") return t("eventConsole.role_user");
  if (role === "assistant") return t("eventConsole.role_assistant");
  if (role === "system") return t("eventConsole.role_system");
  if (role === "tool") return t("eventConsole.role_tool");
  return role;
}

function queueEntryTitle(entry: PendingInputQueueEntry) {
  const content = previewText(String(entry.payload.content || ""), 92);
  if (content) {
    return content;
  }
  const commandName = String(entry.payload.command_name || "").trim();
  if (commandName) {
    return `/${commandName}`;
  }
  return t("eventConsole.queued_turn");
}

function eventToneClass(event: ExecutionEvent) {
  if (
    event.type === "input.queued" ||
    event.type === "input.dequeued" ||
    event.type === "queue.interrupted_turn_superseded" ||
    (event.type === "runtime.interrupt_requested" &&
      String(event.payload?.source || "").trim() === "queued_input")
  ) {
    return "queue";
  }
  if (event.type.includes("failed") || event.type.includes("denied")) {
    return "error";
  }
  if (event.type.includes("tool") || event.type.includes("approval")) {
    return "tool";
  }
  return "conversation";
}

function eventToneLabel(event: ExecutionEvent) {
  const tone = eventToneClass(event);
  if (tone === "queue") return t("eventConsole.tone_queue");
  if (tone === "error") return t("eventConsole.tone_error");
  if (tone === "tool") return t("eventConsole.tone_tool");
  return t("eventConsole.tone_event");
}
</script>

<template>
  <section v-if="sessionStore.session" class="event-console-panel">
    <div class="event-console-head">
      <div>
        <strong>{{ t("eventConsole.title") }}</strong>
        <p>
          {{ t("eventConsole.snapshot_label") }} {{ sessionStore.session.last_snapshot?.stage ?? t("eventConsole.none") }}
          · v{{ sessionStore.session.last_snapshot?.version ?? 0 }}
        </p>
      </div>
      <span class="registry-tag light">
        {{ sessionStore.replayTimeline.length > 0 ? t("eventConsole.replay_view") : t("eventConsole.live_view") }}
      </span>
    </div>

    <div class="event-console-stats">
      <article
        v-for="item in transcriptStats"
        :key="item.key"
        class="event-console-stat"
        :class="`is-${item.tone}`"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="event-console-queue">
      <div class="event-console-section-head">
        <strong>{{ t("eventConsole.queued_turns") }}</strong>
        <span>{{ sessionStore.queuedTurnCount }} {{ t("eventConsole.items_pending") }}</span>
      </div>
      <div v-if="queueEntries.length > 0" class="event-console-queue-list">
        <article
          v-for="item in queueEntries"
          :key="item.id"
          class="event-console-queue-item"
        >
          <div class="event-console-queue-head">
            <strong>{{ queueEntryTitle(item) }}</strong>
            <span>{{ formatServerTime(item.created_at) }}</span>
          </div>
          <div class="event-console-queue-meta">
            <span class="registry-tag queue">{{ queueBehaviorLabel(item.queue_behavior) }}</span>
            <span class="registry-tag light">{{ statusLabel(item.busy_status) }}</span>
            <span class="registry-tag light">{{ statusLabel(item.interrupt_policy) }}</span>
          </div>
          <p>{{ item.reason || t("eventConsole.queue_default_reason") }}</p>
        </article>
      </div>
      <div v-else class="settings-empty">{{ t("eventConsole.no_queued_turns") }}</div>
    </div>

    <div class="event-console-transcript">
      <div class="event-console-section-head">
        <strong>{{ t("eventConsole.recent_transcript") }}</strong>
        <span>{{ t("eventConsole.transcript_hint") }}</span>
      </div>
      <div class="event-console-transcript-list">
        <article
          v-for="item in transcriptEntries"
          :key="item.id"
          class="event-console-transcript-item"
        >
          <div class="event-console-transcript-head">
            <div class="event-console-transcript-meta">
              <span class="registry-tag" :class="bucketClass(item.transcript_bucket)">
                {{ bucketLabel(item.transcript_bucket) }}
              </span>
              <span class="event-console-transcript-role">{{ roleLabel(item.role) }}</span>
              <span class="registry-tag light" :class="{ success: item.context_eligible }">
                {{ item.context_eligible ? t("eventConsole.eligible") : t("eventConsole.display_only") }}
              </span>
            </div>
            <span>{{ formatServerTime(item.created_at) }}</span>
          </div>
          <p>{{ item.content }}</p>
        </article>
        <div v-if="transcriptEntries.length === 0" class="settings-empty">{{ t("eventConsole.no_transcript") }}</div>
      </div>
    </div>

    <button type="button" class="event-console-collapse" @click="eventsExpanded = !eventsExpanded">
      <div class="event-console-section-head">
        <strong>{{ t("eventConsole.runtime_events") }}</strong>
        <span>{{ timeline.length }} {{ t("eventConsole.entries_unit") }}</span>
      </div>
      <i :class="['fa-solid', eventsExpanded ? 'fa-chevron-up' : 'fa-chevron-down']"></i>
    </button>

    <div v-if="eventsExpanded" class="event-console-list">
      <article
        v-for="event in timeline"
        :key="`${event.type}-${event.timestamp}-${String(event.payload?.step || '')}`"
        class="event-console-item"
      >
        <div class="event-console-item-head">
          <div class="event-console-item-meta">
            <strong>{{ event.type }}</strong>
            <span class="registry-tag" :class="eventToneClass(event)">{{ eventToneLabel(event) }}</span>
          </div>
          <span>{{ formatServerTime(event.timestamp) }}</span>
        </div>
        <p>{{ eventMessage(event) }}</p>
      </article>
      <div v-if="timeline.length === 0" class="settings-empty">{{ t("eventConsole.no_events") }}</div>
    </div>
  </section>
</template>
