<script setup lang="ts">
import { t } from "../../../services/i18n";
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <h3 class="section-title">{{ t("scanners.title") }}</h3>
      <p class="head-desc">{{ t("scanners.desc") }}</p>
    </div>
    <div class="scanner-grid">
      <article class="scanner-card">
        <i class="fa-solid fa-satellite-dish"></i>
        <span>{{ t("scanners.nuclei") }}</span>
        <small>{{ t("scanners.nuclei_desc") }}</small>
      </article>
      <article class="scanner-card">
        <i class="fa-solid fa-database"></i>
        <span>{{ t("scanners.sqlmap") }}</span>
        <small>{{ t("scanners.sqlmap_desc") }}</small>
      </article>
      <article class="scanner-card">
        <i class="fa-solid fa-bug"></i>
        <span>{{ t("scanners.xsstrike") }}</span>
        <small>{{ t("scanners.xsstrike_desc") }}</small>
      </article>
      <article class="scanner-card">
        <i class="fa-solid fa-bolt"></i>
        <span>{{ t("scanners.fuzzing") }}</span>
        <small>{{ t("scanners.fuzzing_desc") }}</small>
      </article>
    </div>
  </div>
</template>

<style scoped>
.tools-tab-pane {
  animation: fadeIn 0.3s ease;
}

.pane-header {
  margin-bottom: 24px;
}

.pane-header .section-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.pane-header .head-desc {
  margin: 0;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>