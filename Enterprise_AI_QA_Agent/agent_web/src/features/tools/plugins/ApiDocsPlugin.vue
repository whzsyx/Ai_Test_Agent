<script setup lang="ts">
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <h3 class="section-title">API 接口文档 (API Specifications)</h3>
      <p class="head-desc">统一管理 OpenAPI、Swagger 及 Postman 集合，为 Agent 提供精准的接口级测试知识。</p>
    </div>
    <div class="api-docs-list">
      <article class="api-doc-card">
        <div class="api-doc-header-row">
          <div class="api-doc-icon"><i class="fa-solid fa-file-code"></i></div>
          <div class="api-doc-actions">
            <button class="icon-btn" title="查阅"><i class="fa-regular fa-eye"></i></button>
            <button class="icon-btn" title="同步"><i class="fa-solid fa-rotate"></i></button>
            <button class="icon-btn danger" title="删除"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        </div>
        <div class="api-doc-content">
          <div class="api-doc-head">
            <h4>Core Business API (v2.1)</h4>
            <span class="badge badge-blue">OpenAPI 3.0</span>
          </div>
          <p>涵盖用户认证、权限管理、订单流转及支付回调等核心业务逻辑接口。</p>
          <div class="api-doc-meta">
            <div class="meta-item"><i class="fa-solid fa-link"></i> 142 个接口</div>
            <div class="meta-item"><i class="fa-regular fa-clock"></i> 2026-04-10</div>
          </div>
        </div>
      </article>

      <article class="api-doc-card">
        <div class="api-doc-header-row">
          <div class="api-doc-icon postman"><i class="fa-solid fa-rocket"></i></div>
          <div class="api-doc-actions">
            <button class="icon-btn" title="查阅"><i class="fa-regular fa-eye"></i></button>
            <button class="icon-btn" title="同步"><i class="fa-solid fa-rotate"></i></button>
            <button class="icon-btn danger" title="删除"><i class="fa-solid fa-trash-can"></i></button>
          </div>
        </div>
        <div class="api-doc-content">
          <div class="api-doc-head">
            <h4>Admin Management Services</h4>
            <span class="badge badge-orange">Postman Collection</span>
          </div>
          <p>后台管理系统专用接口集合，包含系统配置与操作日志查询 API。</p>
          <div class="api-doc-meta">
            <div class="meta-item"><i class="fa-solid fa-link"></i> 45 个接口</div>
            <div class="meta-item"><i class="fa-regular fa-clock"></i> 2026-03-25</div>
          </div>
        </div>
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

.api-docs-list {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.api-doc-card {
  display: flex;
  flex-direction: column;
  width: 300px;
  height: 350px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  transition: all 0.2s ease;
  position: relative;
  box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}

.api-doc-card:hover {
  border-color: var(--border-strong);
  box-shadow: 0 12px 24px rgba(0,0,0,0.06);
  transform: translateY(-2px);
}

.api-doc-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.api-doc-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
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
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
}

.api-doc-head h4 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
}

.api-doc-content p {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: var(--muted);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.api-doc-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  font-family: var(--font-mono, monospace);
}

.meta-item i {
  color: var(--border-strong);
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  display: inline-block;
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
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.api-doc-card:hover .api-doc-actions {
  opacity: 1;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.icon-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
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