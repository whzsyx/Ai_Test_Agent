<template>
  <div class="custom-home">
    <!-- Hero Section -->
    <div class="hero-wrapper">
      <div class="hero-grid"></div>
      <div class="hero-fade"></div>
      
      <div class="hero-content">
        <!-- Left Side: Typography -->
        <div class="hero-left">
          <div class="kicker">ENTERPRISE AI QA AGENT</div>
          <h1 class="main-title">御策天检</h1>
          <h2 class="sub-title">面向企业 QA 的 Agent 工作台文档中心</h2>
          <p class="description">
            从快速启动、测试模式、运行时可观测到二次开发规范，<br>
            把多 Agent 编排平台的核心能力拆成可阅读、可执行、可扩展的路径。
          </p>
          
          <div class="actions">
            <a href="/docs/1._系统概述" class="btn primary">阅读开发手册</a>
            <a href="/docs/2._整体架构" class="btn secondary">查看架构图</a>
          </div>
          
          <div class="stats">
            <div class="stat-item">
              <span class="stat-label">当前覆盖</span>
              <div class="stat-value-group">
                <span class="stat-number">7</span>
                <span class="stat-label">测试模式</span>
              </div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-label">运行主线</span>
              <span class="stat-text">Registry · Graph · Runtime</span>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-item">
              <span class="stat-label">知识沉淀</span>
              <span class="stat-text">Memgraph + PostgreSQL</span>
            </div>
          </div>
        </div>

        <!-- Right Side: Runtime Console -->
        <div class="hero-right">
          <div class="console-window">
            <div class="console-header">
              <div class="status-light"></div>
              <span class="status-text">Runtime Online</span>
              <span class="status-badge">SSE / Approval</span>
            </div>
            
            <div class="console-body">
              <div class="log-line"><span class="log-tag log-gray">[session]</span> id=qa_20260601</div>
              <div class="log-line"><span class="log-tag log-light">[mode]</span> ui_automation / api_testing / code_review</div>
              <div class="log-line"><span class="log-tag log-teal">[tool]</span> playwright_cli aria_snapshot completed</div>
              <div class="log-line"><span class="log-tag log-yellow">[approval]</span> terminal command requires human review</div>
              <div class="log-line"><span class="log-tag log-blue">[artifact]</span> ui_explorer_graph.json stored</div>
            </div>

            <div class="doc-paths-section">
              <div class="doc-path-title">文档路径</div>
              <div class="doc-paths">
                <a href="/docs/3._快速开始" class="doc-path-card">
                  <div class="card-title">快速开始</div>
                  <div class="card-desc">3 min setup</div>
                </a>
                <a href="/docs/5._测试模式详解" class="doc-path-card">
                  <div class="card-title">测试模式</div>
                  <div class="card-desc">7 modes</div>
                </a>
                <a href="/docs/12._二次开发指南" class="doc-path-card">
                  <div class="card-title">二次开发</div>
                  <div class="card-desc">registry first</div>
                </a>
              </div>
            </div>

            <div class="console-footer">
              页面知识图谱：Page · Element · Entity · REVEALS
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Section 1: Quick Routes -->
    <section class="section-container">
      <div class="section-header">
        <h2 class="section-title">先解决读者的第一件事</h2>
        <p class="section-desc">首页不堆概念，而是把新用户、开发者、维护者分别送到正确入口。</p>
      </div>
      
      <div class="quick-routes">
        <div class="route-card">
          <div class="route-icon dark-bg">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
          </div>
          <h3 class="route-title">快速启动</h3>
          <p class="route-desc">后端 FastAPI、前端 Vite、文档 VitePress。</p>
          <div class="route-code">
            <div>cd Agent_Server · uvicorn src.main:app</div>
            <div class="muted">cd agent_web · npm run docs:dev</div>
          </div>
        </div>
        
        <div class="route-card">
          <div class="route-icon teal-bg">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
          </div>
          <h3 class="route-title">理解运行时</h3>
          <p class="route-desc">会话、事件、快照、审批、工具任务全程可观测。</p>
          <div class="route-pills">
            <span class="pill">Session</span>
            <span class="pill">SSE</span>
            <span class="pill">Approval</span>
          </div>
        </div>
        
        <div class="route-card">
          <div class="route-icon blue-bg">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
          </div>
          <h3 class="route-title">扩展新能力</h3>
          <p class="route-desc">新增 Mode、Agent、Tool、Skill、MCP 都走统一注册。</p>
          <div class="route-code">
            <div>registry → manifest → runtime</div>
            <div class="muted">保持 Harness Engineering 约束</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 2: Architecture Strip -->
    <section class="section-container">
      <div class="arch-strip">
        <div class="arch-content">
          <h2 class="arch-title">平台主线一眼看懂</h2>
          <p class="arch-desc">文档首页用一条运行链路解释系统，不让读者先陷进目录。</p>
          
          <div class="arch-flow">
            <div class="flow-node">前端工作台</div>
            <div class="flow-arrow"></div>
            <div class="flow-node">FastAPI 接口</div>
            <div class="flow-arrow"></div>
            <div class="flow-node active">LangGraph</div>
            <div class="flow-arrow"></div>
            <div class="flow-node">Tool Runtime</div>
            <div class="flow-arrow"></div>
            <div class="flow-node">证据 / 图谱 / 报告</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 3: Mode Index -->
    <section class="section-container mode-section">
      <div class="section-header">
        <h2 class="section-title">测试模式入口</h2>
        <p class="section-desc">首页底部给出模式地图，让读者快速判断自己该读哪一章。</p>
      </div>
      
      <div class="mode-grid">
        <div class="mode-pill"><span class="dot green"></span>默认协作</div>
        <div class="mode-pill"><span class="dot teal"></span>UI 探索</div>
        <div class="mode-pill"><span class="dot blue"></span>API 测试</div>
        <div class="mode-pill"><span class="dot red"></span>安全测试</div>
        <div class="mode-pill"><span class="dot yellow"></span>代码审批</div>
        <div class="mode-pill"><span class="dot gray"></span>性能占位</div>
        <div class="mode-pill"><span class="dot gray"></span>冒烟占位</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Base Styles matching the Prototype */
.custom-home {
  font-family: Inter, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
  color: #101318;
  background-color: #fbfcfd;
  min-height: 100vh;
  padding-bottom: 120px;
  transition: background-color 0.4s ease, color 0.4s ease;
}

.dark .custom-home {
  background-color: #0e1218;
  color: #f8fafc;
}

/* Typography Helpers */
.muted { color: #697281; transition: color 0.4s ease; }
.dark .muted { color: #94a3b8; }

/* Hero Section */
.hero-wrapper {
  position: relative;
  width: 100%;
  min-height: 610px;
  overflow: hidden;
  padding: 80px 24px;
}

.hero-grid {
  position: absolute;
  top: 0; left: 0; right: 0; height: 100%;
  background-image: linear-gradient(#e7edf3 1px, transparent 1px), linear-gradient(90deg, #e7edf3 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.8;
  z-index: 1;
  transition: background-image 0.4s ease;
}

.dark .hero-grid {
  background-image: linear-gradient(#1e293b 1px, transparent 1px), linear-gradient(90deg, #1e293b 1px, transparent 1px);
}

.hero-fade {
  position: absolute;
  top: 0; left: 0; right: 0; height: 100%;
  background: linear-gradient(to bottom, #ffffff 0%, rgba(247, 250, 252, 0.8) 55%, rgba(238, 244, 248, 0) 100%);
  opacity: 0.86;
  z-index: 2;
  transition: background 0.4s ease;
}

.dark .hero-fade {
  background: linear-gradient(to bottom, #0e1218 0%, rgba(15, 23, 42, 0.8) 55%, rgba(15, 23, 42, 0) 100%);
}

.hero-content {
  position: relative;
  z-index: 10;
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  gap: 64px;
  align-items: center;
}

.hero-left {
  flex: 1;
}

.kicker {
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 2px;
  color: #0f766e;
  margin-bottom: 24px;
  transition: color 0.4s ease;
}

.dark .kicker { color: #2dd4bf; }

.main-title {
  font-size: 86px;
  font-weight: 850;
  letter-spacing: -2px;
  margin: 0 0 16px 0;
  line-height: 1;
  color: #101318;
  transition: color 0.4s ease;
}

.dark .main-title { color: #ffffff; }

.sub-title {
  font-size: 38px;
  font-weight: 780;
  letter-spacing: -0.5px;
  margin: 0 0 24px 0;
  line-height: 1.2;
  color: #101318;
  transition: color 0.4s ease;
}

.dark .sub-title { color: #f1f5f9; }

.description {
  font-size: 18px;
  line-height: 1.6;
  color: #697281;
  margin: 0 0 40px 0;
  transition: color 0.4s ease;
}

.dark .description { color: #94a3b8; }

.actions {
  display: flex;
  gap: 16px;
  margin-bottom: 64px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  border-radius: 24px;
  font-size: 14px;
  font-weight: 750;
  padding: 0 28px;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.btn.primary {
  background-color: #0e1218;
  color: #ffffff;
}

.dark .btn.primary {
  background-color: #f8fafc;
  color: #0f172a;
}

.btn.secondary {
  background-color: #ffffff;
  color: #101318;
  border: 1px solid #dfe5ec;
}

.dark .btn.secondary {
  background-color: transparent;
  color: #f8fafc;
  border-color: #334155;
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.1);
}

.stats {
  display: flex;
  align-items: flex-end;
  gap: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 14px;
  color: #697281;
  transition: color 0.4s ease;
}

.dark .stat-label { color: #94a3b8; }

.stat-value-group {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stat-number {
  font-size: 38px;
  font-weight: 780;
  line-height: 1;
  color: #101318;
  transition: color 0.4s ease;
}

.dark .stat-number { color: #f8fafc; }

.stat-text {
  font-size: 22px;
  font-weight: 780;
  color: #101318;
  transition: color 0.4s ease;
}

.dark .stat-text { color: #f8fafc; }

.stat-divider {
  width: 1px;
  height: 60px;
  background-color: #dfe5ec;
  margin-bottom: 4px;
  transition: background-color 0.4s ease;
}

.dark .stat-divider { background-color: #334155; }

/* Console Window */
.hero-right {
  flex: 1;
  max-width: 500px;
}

.console-window {
  background-color: #ffffff;
  border: 1px solid #dce3eb;
  border-radius: 26px;
  padding: 22px;
  box-shadow: 0 22px 44px -12px rgba(15, 23, 42, 0.1);
  transition: background-color 0.4s ease, border-color 0.4s ease, box-shadow 0.4s ease, transform 0.4s ease;
}

.console-window:hover {
  transform: translateY(-4px);
  box-shadow: 0 30px 60px -15px rgba(15, 23, 42, 0.15);
}

.dark .console-window {
  background-color: #0f172a;
  border-color: #1e293b;
  box-shadow: 0 22px 44px -12px rgba(0, 0, 0, 0.5);
}

.console-header {
  background-color: #f2f5f8;
  border-radius: 16px;
  height: 54px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 12px;
  margin-bottom: 22px;
  transition: background-color 0.4s ease;
}

.dark .console-header { background-color: #1e293b; }

.status-light {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background-color: #16a34a;
}

.status-text {
  font-size: 14px;
  font-weight: 800;
  color: #101318;
  flex: 1;
  transition: color 0.4s ease;
}

.dark .status-text { color: #f8fafc; }

.status-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: #697281;
}

.console-body {
  background: linear-gradient(to bottom right, #0d1117, #1a202b);
  border-radius: 18px;
  padding: 24px;
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  margin-bottom: 24px;
}

.log-line {
  margin-bottom: 12px;
  color: #e5e7eb;
}
.log-line:last-child { margin-bottom: 0; }
.log-gray { color: #94a3b8; }
.log-light { color: #e5e7eb; }
.log-teal { color: #5eead4; }
.log-yellow { color: #fbbf24; }
.log-blue { color: #93c5fd; }

.doc-paths-section {
  margin-bottom: 24px;
}

.doc-path-title {
  font-size: 14px;
  color: #697281;
  margin-bottom: 12px;
  transition: color 0.4s ease;
}

.doc-paths {
  display: flex;
  gap: 12px;
}

.doc-path-card {
  flex: 1;
  background-color: #f8fafc;
  border: 1px solid #dfe5ec;
  border-radius: 14px;
  padding: 16px 12px;
  text-decoration: none;
  transition: all 0.3s ease;
}

.dark .doc-path-card {
  background-color: #0f172a;
  border-color: #1e293b;
}

.doc-path-card:hover {
  border-color: #0f766e;
  transform: translateY(-4px);
  box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05);
}

.card-title {
  font-size: 14px;
  font-weight: 800;
  color: #101318;
  margin-bottom: 4px;
  transition: color 0.4s ease;
}

.dark .card-title { color: #f8fafc; }

.card-desc {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: #697281;
  transition: color 0.4s ease;
}

.console-footer {
  background-color: #eefdf9;
  border: 1px solid #b7eee1;
  border-radius: 16px;
  height: 52px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 800;
  color: #0f766e;
  transition: all 0.4s ease;
}

.dark .console-footer {
  background-color: rgba(15, 118, 110, 0.1);
  border-color: rgba(45, 212, 191, 0.2);
  color: #2dd4bf;
}

/* Sections Global */
.section-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 60px 24px;
}

.section-header {
  margin-bottom: 48px;
}

.section-title {
  font-size: 38px;
  font-weight: 780;
  letter-spacing: -0.5px;
  color: #101318;
  margin: 0 0 16px 0;
  transition: color 0.4s ease;
}

.dark .section-title { color: #f8fafc; }

.section-desc {
  font-size: 18px;
  color: #697281;
  margin: 0;
  transition: color 0.4s ease;
}

/* Quick Routes */
.quick-routes {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.route-card {
  background-color: #ffffff;
  border: 1px solid #dfe5ec;
  border-radius: 12px;
  padding: 26px;
  transition: all 0.3s ease;
}

.route-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 30px -10px rgba(0,0,0,0.08);
  border-color: #cbd5e1;
}

.dark .route-card {
  background-color: #0f172a;
  border-color: #1e293b;
}

.dark .route-card:hover {
  border-color: #334155;
  box-shadow: 0 12px 30px -10px rgba(0,0,0,0.5);
}

.route-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dark-bg { background-color: #0e1218; }
.teal-bg { background-color: #0f766e; }
.blue-bg { background-color: #2563eb; }

.dark .dark-bg { background-color: #334155; }

.route-title {
  font-size: 22px;
  font-weight: 760;
  color: #101318;
  margin: 0 0 12px 0;
  transition: color 0.4s ease;
}

.dark .route-title { color: #f8fafc; }

.route-desc {
  font-size: 14px;
  color: #697281;
  margin: 0 0 32px 0;
  line-height: 1.5;
  transition: color 0.4s ease;
}

.route-code {
  font-family: "JetBrains Mono", monospace;
  font-size: 14px;
  color: #101318;
  transition: color 0.4s ease;
}

.dark .route-code { color: #f8fafc; }

.route-pills {
  display: flex;
  gap: 8px;
}

.pill {
  background-color: #f1f5f9;
  color: #697281;
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 14px;
  transition: all 0.4s ease;
}

.dark .pill {
  background-color: #1e293b;
  color: #94a3b8;
}

/* Arch Strip */
.arch-strip {
  background-color: #0e1218;
  border-radius: 10px;
  padding: 48px;
  transition: background-color 0.4s ease;
}

.dark .arch-strip { background-color: #161b22; }

.arch-title {
  font-size: 38px;
  font-weight: 780;
  color: #ffffff;
  margin: 0 0 16px 0;
}

.arch-desc {
  font-size: 18px;
  color: #a9b4c2;
  margin: 0 0 40px 0;
}

.arch-flow {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.flow-node {
  background-color: #161b23;
  border: 1px solid #2f3743;
  border-radius: 8px;
  padding: 0 24px;
  height: 58px;
  display: flex;
  align-items: center;
  color: #ffffff;
  font-size: 14px;
  font-weight: 800;
  transition: all 0.3s ease;
}

.flow-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}

.flow-node.active {
  background-color: #0f766e;
  border-color: #0f766e;
}

.flow-node.active:hover {
  box-shadow: 0 4px 15px rgba(15, 118, 110, 0.4);
}

.flow-arrow {
  width: 24px;
  height: 2px;
  background-color: #4b5563;
  position: relative;
}

.flow-arrow::after {
  content: '';
  position: absolute;
  right: 0;
  top: -4px;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 5px solid #4b5563;
}

/* Mode Index */
.mode-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.mode-pill {
  display: flex;
  align-items: center;
  gap: 12px;
  background-color: #ffffff;
  border: 1px solid #dfe5ec;
  border-radius: 8px;
  padding: 0 20px;
  height: 58px;
  font-size: 14px;
  font-weight: 760;
  color: #101318;
  transition: all 0.3s ease;
  cursor: pointer;
}

.mode-pill:hover {
  transform: translateY(-3px);
  border-color: #94a3b8;
  box-shadow: 0 6px 15px -3px rgba(0,0,0,0.05);
}

.dark .mode-pill {
  background-color: #0f172a;
  border-color: #1e293b;
  color: #f8fafc;
}

.dark .mode-pill:hover {
  border-color: #475569;
  box-shadow: 0 6px 15px -3px rgba(0,0,0,0.3);
}

.mode-pill .dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.dot.green { background-color: #16a34a; }
.dot.teal { background-color: #0f766e; }
.dot.blue { background-color: #2563eb; }
.dot.red { background-color: #dc2626; }
.dot.yellow { background-color: #b45309; }
.dot.gray { background-color: #94a3b8; }

/* =========================================
   ENTRANCE ANIMATIONS (Fade In Up)
   ========================================= */

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.hero-left .kicker { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; opacity: 0; animation-delay: 0.1s; }
.hero-left .main-title { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; opacity: 0; animation-delay: 0.2s; }
.hero-left .sub-title { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; opacity: 0; animation-delay: 0.3s; }
.hero-left .description { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; opacity: 0; animation-delay: 0.4s; }
.hero-left .actions { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; opacity: 0; animation-delay: 0.5s; }
.hero-left .stats { animation: fadeInUp 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; opacity: 0; animation-delay: 0.6s; }

.hero-right .console-window {
  animation: fadeInUp 1s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  opacity: 0;
  animation-delay: 0.3s;
}

.section-container {
  animation: fadeInUp 1s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  opacity: 0;
  animation-delay: 0.4s;
}

/* Responsive Adjustments */
@media (max-width: 1024px) {
  .hero-content {
    flex-direction: column;
    text-align: center;
  }
  .actions {
    justify-content: center;
  }
  .stats {
    justify-content: center;
  }
  .stat-divider { display: none; }
  .stats { flex-direction: column; gap: 16px; align-items: center; }
  .quick-routes { grid-template-columns: 1fr; }
  .arch-flow { justify-content: center; }
}
</style>
