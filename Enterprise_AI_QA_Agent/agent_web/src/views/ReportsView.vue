<template>
  <section class="view-page report-page">
    <header class="page-head">
      <div class="head-content">
        <h2>Execution Reports</h2>
        <p class="head-desc">综合评估报告与多报告聚合分析，包含质量评级与改进建议。</p>
      </div>
      <div class="head-actions">
        <button class="primary-btn"><i class="fa-regular fa-paper-plane"></i> Send Report</button>
      </div>
    </header>

    <div class="report-layout">
      <!-- Sidebar: Batches -->
      <aside class="report-sidebar">
        <div class="sidebar-header">
          <h3>Recent Batches</h3>
        </div>
        <div class="batch-list">
          <article class="batch-item active">
            <div class="batch-item-header">
              <span class="batch-id">#Run-20260311-A</span>
              <span class="badge badge-green">Grade A</span>
            </div>
            <p class="batch-meta mono">12 Functional, 1 Security</p>
            <div class="batch-stats">
              <span class="stat pass"><i class="fa-solid fa-check"></i> 11 Passed</span>
              <span class="stat fail"><i class="fa-solid fa-xmark"></i> 1 Failed</span>
            </div>
          </article>

          <article class="batch-item">
            <div class="batch-item-header">
              <span class="batch-id">#Run-20260310-B</span>
              <span class="badge badge-red">Grade C</span>
            </div>
            <p class="batch-meta mono">45 Full Regression</p>
            <div class="batch-stats">
              <span class="stat pass"><i class="fa-solid fa-check"></i> 38 Passed</span>
              <span class="stat fail"><i class="fa-solid fa-xmark"></i> 7 Failed</span>
            </div>
          </article>
        </div>
      </aside>

      <!-- Main Content: Report Detail -->
      <main class="report-detail">
        <div class="detail-header">
          <div class="detail-title">
            <div class="title-row">
              <h3>Batch #Run-20260311-A</h3>
              <span class="grade-box">A</span>
            </div>
            <p class="detail-desc"><i class="fa-solid fa-robot"></i> AI Aggregated Diagnostics completed in 4m 12s.</p>
          </div>
        </div>

        <div class="detail-content">
          <!-- Section: Error Analysis -->
          <section class="content-section">
            <div class="section-header">
              <h4>异常用例剖析</h4>
              <span class="subtitle mono">Element Mismatch</span>
            </div>
            
            <div class="error-card">
              <div class="error-card-header">
                <div class="error-case">
                  <i class="fa-solid fa-bug text-red"></i>
                  <span>点击 '忘记密码' 链接 (CASE-1021)</span>
                </div>
                <button class="secondary-btn small-btn"><i class="fa-solid fa-arrow-up-right-from-square"></i> 推送至禅道</button>
              </div>
              <p class="error-text">
                Agent 尝试基于历史知识库定位 '忘记密码' 链接，但目标页面的 DOM 结构已发生变更。执行中断以防误操作。
              </p>
              
              <div class="diff-grid">
                <div class="diff-panel old">
                  <div class="diff-badge">知识库参考 (旧)</div>
                  <div class="diff-body mono">
                    <span class="label">Text:</span> "Forgot Password?"
                  </div>
                </div>
                <div class="diff-panel new">
                  <div class="diff-badge">实时 DOM 抓取 (新)</div>
                  <div class="diff-body mono">
                    <span class="label">Selector:</span> a.text-sm.reset-link<br />
                    <span class="label">Text:</span> "Reset password"
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Section: Suggestions -->
          <section class="content-section">
            <div class="section-header">
              <h4>AI 修复建议</h4>
              <span class="subtitle mono">Suggestions</span>
            </div>
            <ul class="suggestion-list">
              <li>
                <i class="fa-solid fa-lightbulb text-yellow"></i>
                <p>使用新的选择器 <code>a.text-sm.reset-link</code> 更新知识库向量 <strong>#4928</strong>。</p>
              </li>
              <li>
                <i class="fa-solid fa-shield-halved text-blue"></i>
                <p>系统 API <code>/api/admin/users</code> 安全扫描未发现越权，但检测到响应头缺少 <code>Strict-Transport-Security</code>，建议补充基线配置。</p>
              </li>
            </ul>
          </section>
        </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px 32px;
  background: var(--bg);
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.head-content h2 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 6px 0;
  letter-spacing: -0.02em;
}

.head-desc {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

.report-layout {
  display: flex;
  flex: 1;
  gap: 24px;
  min-height: 0;
}

/* Sidebar */
.report-sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  padding-right: 24px;
  flex-shrink: 0;
}

.sidebar-header h3 {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin: 0 0 16px 0;
}

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.batch-item {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  cursor: pointer;
  transition: all 0.2s ease;
}

.batch-item:hover {
  background: var(--surface-muted);
}

.batch-item.active {
  background: var(--surface);
  border-color: var(--border-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.batch-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.batch-id {
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}

.badge-green {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.badge-red {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.batch-meta {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 12px 0;
}

.batch-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  font-weight: 500;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat.pass { color: #16a34a; }
.stat.fail { color: #dc2626; }

/* Main Content */
.report-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-right: 8px;
}

.detail-header {
  margin-bottom: 32px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.title-row h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.grade-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #16a34a;
  color: white;
  font-weight: 700;
  font-size: 16px;
}

.detail-desc {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.content-section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.section-header h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.section-header .subtitle {
  font-size: 13px;
  color: var(--muted);
}

/* Error Card */
.error-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}

.error-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.error-case {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.text-red { color: #dc2626; }
.text-yellow { color: #d97706; }
.text-blue { color: #2563eb; }

.small-btn {
  padding: 6px 12px;
  font-size: 12px;
}

.error-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
  margin: 0 0 20px 0;
}

/* Diff Grid */
.diff-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.diff-panel {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.diff-panel.old {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.02);
}

.diff-panel.new {
  border-color: rgba(34, 197, 94, 0.2);
  background: rgba(34, 197, 94, 0.02);
}

.diff-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-soft);
}

.diff-panel.old .diff-badge {
  color: #dc2626;
  border-bottom-color: rgba(239, 68, 68, 0.1);
  background: rgba(239, 68, 68, 0.05);
}

.diff-panel.new .diff-badge {
  color: #16a34a;
  border-bottom-color: rgba(34, 197, 94, 0.1);
  background: rgba(34, 197, 94, 0.05);
}

.diff-body {
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
}

.diff-body .label {
  color: var(--muted);
  user-select: none;
}

/* Suggestions */
.suggestion-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-list li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.suggestion-list i {
  margin-top: 2px;
  font-size: 16px;
}

.suggestion-list p {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
}

.suggestion-list code {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  background: var(--surface);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
}

.mono {
  font-family: var(--font-mono, monospace);
}
</style>
