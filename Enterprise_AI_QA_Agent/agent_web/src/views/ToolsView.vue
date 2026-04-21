<script setup lang="ts">
import { computed, ref } from "vue";
import { toolsPlugins, type ToolsPluginDefinition, type ToolsPluginKey } from "../features/tools/plugins";

const defaultPlugin = toolsPlugins[0];
const activeTab = ref<ToolsPluginKey>(defaultPlugin.key);

const activePlugin = computed(
  () => toolsPlugins.find((item) => item.key === activeTab.value) ?? defaultPlugin,
);
</script>

<template>
  <section class="view-page tools-page">
    <div class="page-head">
      <div>
        <h2>Skills 与工具管理</h2>
        <p class="head-desc">管理 Agent 增强知识、漏洞扫描引擎及后端已注册工具链</p>
      </div>
      <div class="page-head-actions">
        <template v-if="activeTab === 'skills'">
          <button class="secondary-btn"><i class="fa-brands fa-github"></i> Github 导入</button>
          <button class="primary-btn"><i class="fa-solid fa-upload"></i> 上传技能包</button>
        </template>
        <template v-else-if="activeTab === 'apidocs'">
          <button class="primary-btn"><i class="fa-solid fa-plus"></i> 添加文档源</button>
        </template>
      </div>
    </div>

    <!-- 二级导航栏 -->
    <nav class="tools-secondary-nav">
      <button 
        v-for="plugin in toolsPlugins" 
        :key="plugin.key"
        class="tools-tab-btn" 
        :class="{ active: activeTab === plugin.key }"
        @click="activeTab = plugin.key"
      >
        <i :class="[`fa-${plugin.iconType}`, plugin.icon]"></i>
        <span>{{ plugin.label }}</span>
      </button>
    </nav>

    <!-- Tab 内容区域 -->
    <div class="tools-content-area">
      <component :is="activePlugin.component" />
    </div>
  </section>
</template>

<style scoped>
.tools-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px 32px;
}

.page-head {
  margin-bottom: 16px;
  padding-bottom: 12px;
}

.page-head h2 {
  font-size: 24px;
  margin-bottom: 4px;
}

.head-desc {
  font-size: 13px;
  margin: 0;
}

.tools-secondary-nav {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.tools-tab-btn {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: color 0.2s, border-color 0.2s;
  margin-bottom: -1px;
}

.tools-tab-btn i {
  font-size: 15px;
}

.tools-tab-btn:hover {
  color: var(--text);
}

.tools-tab-btn.active {
  color: var(--blue);
  border-bottom-color: var(--blue);
}

.tools-content-area {
  flex: 1;
  overflow-y: auto;
}

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

.flex-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.api-docs-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.api-doc-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  transition: all 0.2s ease;
}

.api-doc-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-soft);
}

.api-doc-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.api-doc-icon.postman {
  background: rgba(249, 115, 22, 0.1);
  color: #f97316;
}

.api-doc-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.api-doc-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}

.api-doc-head h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.api-doc-content p {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--muted);
  line-height: 1.5;
}

.api-doc-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.muted-divider {
  color: var(--border-strong);
  font-size: 12px;
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}

.badge-blue {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.badge-orange {
  background: rgba(249, 115, 22, 0.1);
  color: #ea580c;
}

.api-doc-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}

.small-btn {
  padding: 6px 12px;
  font-size: 13px;
}

.registry-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 0;
  color: var(--muted);
  background: var(--surface-muted);
  border-radius: 12px;
  border: 1px dashed var(--border);
}

.registry-empty i {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
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