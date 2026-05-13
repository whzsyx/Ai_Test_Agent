<script setup lang="ts">
import { computed } from "vue";

import { t } from "../../services/i18n";
import { useSessionStore } from "../../stores/session";

const sessionStore = useSessionStore();

const results = computed(() => {
  const primary = sessionStore.verificationMeta?.verification_results;
  if (Array.isArray(primary) && primary.length > 0) {
    return primary.slice().reverse().slice(0, 8);
  }
  return (sessionStore.session?.verification_results ?? []).slice().reverse().slice(0, 8);
});

function tone(status: string) {
  if (status === "passed") return "online";
  if (status === "partial" || status === "not_run") return "degraded";
  return "offline";
}

function statusLabel(status: string) {
  switch (status) {
    case "passed":
      return t("verification.passed");
    case "failed":
      return t("verification.failed");
    case "partial":
      return t("verification.partial");
    case "not_run":
      return t("verification.not_run");
    default:
      return status;
  }
}
</script>

<template>
  <section v-if="sessionStore.session" class="observability-panel verification-panel">
    <div class="observability-head">
      <div>
        <strong>{{ t("verification.title") }}</strong>
        <p>{{ t("verification.desc") }}</p>
      </div>
      <span class="registry-tag light">{{ results.length }} {{ t("verification.results_unit") }}</span>
    </div>

    <div v-if="results.length" class="tool-activity-list">
      <article v-for="item in results" :key="item.id" class="tool-activity-item">
        <div class="tool-activity-head">
          <div>
            <strong>{{ item.verifier }}</strong>
            <p>{{ item.summary }}</p>
          </div>
          <span :class="['runtime-status-square-dot', `is-${tone(item.status)}`]"></span>
        </div>
        <dl class="tool-activity-grid">
          <div>
            <dt>{{ t("verification.status") }}</dt>
            <dd>{{ statusLabel(item.status) }}</dd>
          </div>
          <div>
            <dt>{{ t("verification.assertion_count") }}</dt>
            <dd>{{ item.assertion_count }}</dd>
          </div>
          <div>
            <dt>{{ t("verification.passed") }}</dt>
            <dd>{{ item.passed_count }}</dd>
          </div>
          <div>
            <dt>{{ t("verification.failed") }}</dt>
            <dd>{{ item.failed_count }}</dd>
          </div>
          <div v-if="item.evidence?.length">
            <dt>{{ t("verification.evidence") }}</dt>
            <dd>{{ item.evidence.length }}</dd>
          </div>
        </dl>
      </article>
    </div>

    <div v-else class="settings-empty">{{ t("verification.empty") }}</div>
  </section>
</template>
