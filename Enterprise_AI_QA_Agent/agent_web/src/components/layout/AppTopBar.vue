<script setup lang="ts">
import { computed } from "vue";

import type { ServiceCheckItem, SystemStatusSummary } from "../../types";
import { t } from "../../services/i18n";

const props = defineProps<{
  label: string;
  systemStatus: SystemStatusSummary;
}>();

const failingChecks = computed(() =>
  props.systemStatus.checks.filter((check) => check.status !== "online"),
);

function statusIcon(check: ServiceCheckItem) {
  if (check.status === "online") {
    return "fa-circle-check";
  }
  if (check.status === "degraded") {
    return "fa-triangle-exclamation";
  }
  return "fa-circle-xmark";
}
</script>

<template>
  <header class="top-status-bar">
    <div class="top-status-path">
      <i class="fa-solid fa-spider"></i>
      <span>{{ t("home.title") }} / {{ props.label }}</span>
    </div>
    <div class="top-status-actions">
      <div class="service-indicator-wrap">
        <span :class="['service-indicator', `is-${props.systemStatus.tone}`]">
          <span class="service-dot"></span>
          <span>{{ props.systemStatus.label }}</span>
          <span class="service-count">
            {{ props.systemStatus.onlineCount }}/{{ props.systemStatus.totalCount }}
          </span>
        </span>
        <div class="service-tooltip">
          <div class="service-tooltip-head">
            <strong>{{ t("status.title") }}</strong>
            <span v-if="failingChecks.length === 0">{{ t("status.all_connected") }}</span>
            <span v-else>{{ t("status.not_ready_count", { count: failingChecks.length }) }}</span>
          </div>
          <div class="service-tooltip-list">
            <div
              v-for="check in props.systemStatus.checks"
              :key="check.key"
              :class="['service-tooltip-item', `is-${check.status}`]"
            >
              <div class="service-tooltip-title">
                <i :class="['fa-solid', statusIcon(check)]"></i>
                <span>{{ check.label }}</span>
              </div>
              <div class="service-tooltip-detail">{{ check.detail }}</div>
              <div v-if="check.meta" class="service-tooltip-meta">{{ check.meta }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
