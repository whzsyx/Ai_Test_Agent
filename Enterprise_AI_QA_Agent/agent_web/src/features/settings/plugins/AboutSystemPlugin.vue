<script setup lang="ts">
import type { SettingsPluginDefinition } from "../plugins";
import { t } from "../../../services/i18n";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();

const repoUrl = "https://github.com/eighteendreamer/Ai_Test_Agent";
const issuesUrl = `${repoUrl}/issues`;
const docsUrl = "http://localhost:5173/manual/1._系统概述.html";

const stackItems = [
  {
    icon: "fa-brands fa-python",
    title: t("about.stack_backend_title"),
    description: t("about.stack_backend_desc"),
  },
  {
    icon: "fa-brands fa-vuejs",
    title: t("about.stack_frontend_title"),
    description: t("about.stack_frontend_desc"),
  },
  {
    icon: "fa-solid fa-diagram-project",
    title: t("about.stack_arch_title"),
    description: t("about.stack_arch_desc"),
  },
  {
    icon: "fa-solid fa-database",
    title: t("about.stack_eng_title"),
    description: t("about.stack_eng_desc"),
  },
];

const highlights = [
  t("about.highlight_1"),
  t("about.highlight_2"),
  t("about.highlight_3"),
];

const infoCards = [
  {
    icon: "fa-solid fa-user-astronaut",
    title: t("about.author_title"),
    value: "eighteendreamer",
    detail: t("about.author_detail"),
  },
  {
    icon: "fa-solid fa-scale-balanced",
    title: t("about.license_title"),
    value: t("about.license_value"),
    detail: t("about.license_detail"),
  },
  {
    icon: "fa-solid fa-comment-dots",
    title: t("about.feedback_title"),
    value: "GitHub Issues",
    detail: t("about.feedback_detail"),
  },
  {
    icon: "fa-solid fa-book-open",
    title: t("about.docs_title"),
    value: "README / docs",
    detail: t("about.docs_detail"),
  },
];
</script>

<template>
  <section class="about-system">
    <header class="about-header">
      <div class="about-header__main">
        <div class="about-logo">
          <i class="fa-solid fa-spider"></i>
        </div>
        <div class="about-title-wrapper">
          <div class="about-eyebrow">Enterprise AI QA Agent</div>
          <h1 class="about-title">{{ t("about.title") }}</h1>
          <p class="about-desc">
        {{ t("about.desc") }}
      </p>
        </div>
      </div>
      
      <div class="about-header__actions">
        <a class="action-btn primary" :href="repoUrl" target="_blank" rel="noreferrer">
          <i class="fa-brands fa-github"></i>
          <span>{{ t("about.repo") }}</span>
        </a>
        <a class="action-btn" :href="issuesUrl" target="_blank" rel="noreferrer">
          <i class="fa-solid fa-bug"></i>
          <span>{{ t("about.feedback") }}</span>
        </a>
        <a class="action-btn" :href="docsUrl" target="_blank" rel="noreferrer">
          <i class="fa-solid fa-book-open"></i>
          <span>{{ t("about.read_docs") }}</span>
        </a>
      </div>
    </header>

    <div class="about-meta">
      <div class="meta-item">
        <span class="meta-label">{{ t("about.meta_position") }}</span>
        <span class="meta-value">QA Agent Workbench</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t("about.meta_frontend") }}</span>
        <span class="meta-value">Vue 3 + Vite</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t("about.meta_backend") }}</span>
        <span class="meta-value">FastAPI + LangGraph</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t("about.meta_repo") }}</span>
        <span class="meta-value">GitHub / Ai_Test_Agent</span>
      </div>
    </div>

    <div class="about-sections">
      <section class="about-section">
        <h2 class="section-title">{{ t("about.section_features") }}</h2>
        <div class="feature-list">
          <div class="feature-item" v-for="item in highlights" :key="item">
            <i class="fa-solid fa-check feature-icon"></i>
            <span>{{ item }}</span>
          </div>
        </div>
        <div class="badge-row">
          <span class="badge"><i class="fa-solid fa-wand-magic-sparkles"></i> Runtime-first</span>
          <span class="badge"><i class="fa-solid fa-shield-halved"></i> Harness-driven</span>
          <span class="badge"><i class="fa-solid fa-sitemap"></i> Multi-agent Ready</span>
        </div>
      </section>

      <section class="about-section">
        <h2 class="section-title">{{ t("about.section_architecture") }}</h2>
        <div class="list-container">
          <div class="list-item" v-for="item in stackItems" :key="item.title">
            <div class="list-item__icon"><i :class="item.icon"></i></div>
            <div class="list-item__content">
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </div>
          </div>
        </div>
      </section>

      <section class="about-section">
        <h2 class="section-title">{{ t("about.section_feedback") }}</h2>
        <div class="list-container">
          <div class="list-item" v-for="item in infoCards" :key="item.title">
            <div class="list-item__icon"><i :class="item.icon"></i></div>
            <div class="list-item__content">
              <div class="list-item__header">
                <h3>{{ item.title }}</h3>
                <span class="list-item__value">{{ item.value }}</span>
              </div>
              <p>{{ item.detail }}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.about-system {
  /* Colors */
  --about-bg: #ffffff;
  --about-bg-subtle: #f8fafc;
  --about-bg-muted: #f1f5f9;
  --about-text-primary: #0f172a;
  --about-text-secondary: #475569;
  --about-text-tertiary: #64748b;
  --about-border: #e2e8f0;
  --about-border-hover: #cbd5e1;

  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 100%;
  color: var(--about-text-primary);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  padding: 8px 0 32px 0;
}

:root[data-theme="dark"] .about-system {
  --about-bg: #0f172a;
  --about-bg-subtle: #1e293b;
  --about-bg-muted: #334155;
  --about-text-primary: #f8fafc;
  --about-text-secondary: #94a3b8;
  --about-text-tertiary: #64748b;
  --about-border: #1e293b;
  --about-border-hover: #334155;
}

/* Header */
.about-header {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 24px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--about-border);
}

.about-header__main {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  flex: 1;
  min-width: 320px;
}

.about-logo {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--about-bg-muted);
  border: 1px solid var(--about-border);
  border-radius: 12px;
  font-size: 24px;
  color: var(--about-text-primary);
}

.about-title-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.about-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--about-text-tertiary);
}

.about-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--about-text-primary);
  line-height: 1.2;
}

.about-desc {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--about-text-secondary);
  max-width: 600px;
}

.about-header__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--about-text-primary);
  background: var(--about-bg);
  border: 1px solid var(--about-border);
  border-radius: 8px;
  text-decoration: none;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: var(--about-bg-subtle);
  border-color: var(--about-border-hover);
}

.action-btn.primary {
  background: var(--about-text-primary);
  color: var(--about-bg);
  border-color: var(--about-text-primary);
}

.action-btn.primary:hover {
  background: var(--about-text-secondary);
  border-color: var(--about-text-secondary);
}

/* Meta Data */
.about-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 20px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--about-border);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--about-text-tertiary);
}

.meta-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--about-text-primary);
}

/* Sections */
.about-sections {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.about-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--about-text-primary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* Feature List */
.feature-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--about-text-secondary);
}

.feature-icon {
  margin-top: 4px;
  font-size: 12px;
  color: var(--about-text-tertiary);
}

.badge-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--about-text-secondary);
  background: var(--about-bg-subtle);
  border: 1px solid var(--about-border);
  border-radius: 6px;
}

.badge i {
  font-size: 11px;
  opacity: 0.8;
}

/* List Container */
.list-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.list-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--about-border);
  border-radius: 12px;
  background: var(--about-bg);
  transition: border-color 0.2s ease;
}

.list-item:hover {
  border-color: var(--about-border-hover);
}

.list-item__icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--about-text-secondary);
  background: var(--about-bg-subtle);
  border-radius: 8px;
  font-size: 15px;
}

.list-item__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.list-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.list-item__content h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--about-text-primary);
}

.list-item__value {
  font-size: 13px;
  font-weight: 500;
  color: var(--about-text-primary);
}

.list-item__content p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--about-text-secondary);
}

@media (max-width: 640px) {
  .about-header__main {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .list-item__header {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>
