<script setup lang="ts">
import type { SettingsPluginDefinition } from "../plugins";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();

const repoUrl = "https://github.com/eighteendreamer/Ai_Test_Agent";
const issuesUrl = `${repoUrl}/issues`;
const docsUrl = `${repoUrl}#readme`;

const stackItems = [
  {
    icon: "fa-brands fa-python",
    title: "后端运行时",
    description: "FastAPI、LangGraph、Pydantic 与 OAuth provider adapter 共同支撑可编排的 Agent 运行时。",
  },
  {
    icon: "fa-brands fa-vuejs",
    title: "前端工作台",
    description: "Vue 3、Vite、Pinia 与 Naive UI 构成可观测、可配置的企业级 QA 工作台。",
  },
  {
    icon: "fa-solid fa-diagram-project",
    title: "系统架构",
    description: "以 registry、graph、runtime 为主线，逐步扩展多 Agent、工具调用、审批与恢复能力。",
  },
  {
    icon: "fa-solid fa-database",
    title: "工程能力",
    description: "聚焦会话、事件、快照、知识与配置中心，让 QA 能力既可扩展也可运营。",
  },
];

const highlights = [
  "企业级 QA Agent 工作台，面向测试编排、知识检索、运行时可观测与报告交付。",
  "支持模型配置、OAuth 授权、MCP 外部接入、审批流与事件回放等核心能力。",
  "当前持续朝多 Agent 协作、工具调用稳定性与 QA 自动化平台化方向演进。",
];

const infoCards = [
  {
    icon: "fa-solid fa-user-astronaut",
    title: "作者",
    value: "eighteendreamer",
    detail: "项目发起与持续迭代维护者。",
  },
  {
    icon: "fa-solid fa-scale-balanced",
    title: "开源许可证",
    value: "暂未声明",
    detail: "仓库根目录当前未发现 LICENSE 文件，建议后续尽快补齐。",
  },
  {
    icon: "fa-solid fa-comment-dots",
    title: "意见反馈",
    value: "GitHub Issues",
    detail: "欢迎提交缺陷、建议与功能请求。",
  },
  {
    icon: "fa-solid fa-book-open",
    title: "系统文档",
    value: "README / docs",
    detail: "包含架构说明、Harness 规范与开发方向。",
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
          <h1 class="about-title">御策天检</h1>
          <p class="about-desc">
            一套面向企业级质量保障场景的 Agent 工作台，强调运行时可观测、能力可编排、系统可扩展。
          </p>
        </div>
      </div>
      
      <div class="about-header__actions">
        <a class="action-btn primary" :href="repoUrl" target="_blank" rel="noreferrer">
          <i class="fa-brands fa-github"></i>
          <span>开源仓库</span>
        </a>
        <a class="action-btn" :href="issuesUrl" target="_blank" rel="noreferrer">
          <i class="fa-solid fa-bug"></i>
          <span>意见反馈</span>
        </a>
        <a class="action-btn" :href="docsUrl" target="_blank" rel="noreferrer">
          <i class="fa-solid fa-book-open"></i>
          <span>阅读文档</span>
        </a>
      </div>
    </header>

    <div class="about-meta">
      <div class="meta-item">
        <span class="meta-label">定位</span>
        <span class="meta-value">QA Agent Workbench</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">前端技术</span>
        <span class="meta-value">Vue 3 + Vite</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">后端技术</span>
        <span class="meta-value">FastAPI + LangGraph</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">代码仓库</span>
        <span class="meta-value">GitHub / Ai_Test_Agent</span>
      </div>
    </div>

    <div class="about-sections">
      <section class="about-section">
        <h2 class="section-title">系统特性</h2>
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
        <h2 class="section-title">技术架构</h2>
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
        <h2 class="section-title">开源与反馈</h2>
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
