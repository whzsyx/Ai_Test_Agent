<script setup lang="ts">
import { ref } from "vue";

const showDetails = ref(false);
const activeNode = ref<any>(null);
const zoomLevel = ref(1);
const activeEntityFilter = ref("Page");

const mockNodes = [
  {
    id: "node-1",
    name: "登录页面 (Login Page)",
    type: "Page",
    typeClass: "page",
    properties: {
      url: "/login",
      status: "Active",
      elements: 24,
      lastUpdated: "2024-05-20"
    },
    relations: [
      { type: "CALLS", target: "/api/auth/login" },
      { type: "COVERED_BY", target: "TC-1001" },
      { type: "CONTAINS", target: "LoginForm 组件" }
    ]
  },
  {
    id: "node-2",
    name: "/api/auth/login",
    type: "API",
    typeClass: "api",
    properties: {
      method: "POST",
      auth: "None",
      timeout: "2000ms",
      lastUpdated: "2024-05-21"
    },
    relations: [
      { type: "CALLED_BY", target: "登录页面 (Login Page)" },
      { type: "COVERED_BY", target: "TC-1001" }
    ]
  },
  {
    id: "node-3",
    name: "TC-1001: 正常登录",
    type: "TestCase",
    typeClass: "testcase",
    properties: {
      priority: "P0",
      status: "Passed",
      author: "QA-1",
      lastUpdated: "2024-05-22"
    },
    relations: [
      { type: "COVERS", target: "登录页面 (Login Page)" },
      { type: "COVERS", target: "/api/auth/login" }
    ]
  }
];

function handleNodeClick(nodeData: any) {
  activeNode.value = nodeData;
  showDetails.value = true;
}

function closeDetails() {
  showDetails.value = false;
  activeNode.value = null;
}

function zoomIn() {
  zoomLevel.value = Math.min(zoomLevel.value + 0.2, 3);
}

function zoomOut() {
  zoomLevel.value = Math.max(zoomLevel.value - 0.2, 0.5);
}

function zoomFit() {
  zoomLevel.value = 1;
}

function setEntityFilter(type: string) {
  activeEntityFilter.value = type;
}
</script>

<template>
  <section class="view-page kg-page">
    <div class="page-head">
      <div>
        <h2>知识图谱 (Knowledge Graph)</h2>
        <p class="head-desc">基于图数据库的系统业务实体化与关系网络拓扑展示</p>
      </div>
      <div class="page-head-actions">
        <div class="search-box">
          <i class="fa-solid fa-magnifying-glass" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--muted);"></i>
          <input type="text" placeholder="搜索实体、关系、属性..." style="padding-left: 36px;" />
        </div>
        <button class="secondary-btn"><i class="fa-solid fa-filter"></i> 筛选</button>
      </div>
    </div>

    <div class="kg-container">
      <!-- 左侧面板：图谱导航/实体分类 -->
      <aside class="kg-sidebar-left">
        <div class="kg-sidebar-header">
          <h3>实体类型</h3>
        </div>
        <ul class="kg-entity-list">
          <li :class="{ active: activeEntityFilter === 'Page' }" @click="setEntityFilter('Page')"><span class="color-dot page"></span> 页面 (Page) <span class="count">124</span></li>
          <li :class="{ active: activeEntityFilter === 'Component' }" @click="setEntityFilter('Component')"><span class="color-dot component"></span> 组件 (Component) <span class="count">856</span></li>
          <li :class="{ active: activeEntityFilter === 'API' }" @click="setEntityFilter('API')"><span class="color-dot api"></span> 接口 (API) <span class="count">342</span></li>
          <li :class="{ active: activeEntityFilter === 'TestCase' }" @click="setEntityFilter('TestCase')"><span class="color-dot testcase"></span> 测试用例 (TestCase) <span class="count">1,205</span></li>
          <li :class="{ active: activeEntityFilter === 'Bug' }" @click="setEntityFilter('Bug')"><span class="color-dot bug"></span> 缺陷 (Bug) <span class="count">45</span></li>
        </ul>
        
        <div class="kg-sidebar-header mt-4">
          <h3>关系类型</h3>
        </div>
        <ul class="kg-relation-list">
          <li><i class="fa-solid fa-arrow-right-long"></i> 包含 (CONTAINS)</li>
          <li><i class="fa-solid fa-arrow-right-long"></i> 调用 (CALLS)</li>
          <li><i class="fa-solid fa-arrow-right-long"></i> 覆盖 (COVERS)</li>
          <li><i class="fa-solid fa-arrow-right-long"></i> 阻塞 (BLOCKS)</li>
        </ul>
      </aside>

      <!-- 中间：图谱可视化主区域 -->
      <main class="kg-canvas-area">
        <div class="kg-canvas-toolbar">
          <button class="icon-btn" title="放大" @click="zoomIn"><i class="fa-solid fa-plus"></i></button>
          <button class="icon-btn" title="缩小" @click="zoomOut"><i class="fa-solid fa-minus"></i></button>
          <button class="icon-btn" title="适应屏幕" @click="zoomFit"><i class="fa-solid fa-expand"></i></button>
        </div>
        
        <!-- 图谱占位，点击可模拟查看详情 -->
        <div class="kg-canvas-placeholder" @click.self="closeDetails" :style="{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center', transition: 'transform 0.2s ease' }">
          <div class="kg-node-mock" style="top: 30%; left: 40%;" @click.stop="handleNodeClick(mockNodes[0])">
            <div class="node-circle page" :class="{ 'is-selected': activeNode?.id === 'node-1' }"></div>
            <span>登录页面</span>
          </div>
          <div class="kg-node-mock" style="top: 60%; left: 30%;" @click.stop="handleNodeClick(mockNodes[1])">
            <div class="node-circle api" :class="{ 'is-selected': activeNode?.id === 'node-2' }"></div>
            <span>/api/auth/login</span>
          </div>
          <div class="kg-node-mock" style="top: 50%; left: 60%;" @click.stop="handleNodeClick(mockNodes[2])">
            <div class="node-circle testcase" :class="{ 'is-selected': activeNode?.id === 'node-3' }"></div>
            <span>TC-1001: 正常登录</span>
          </div>
          
          <svg class="kg-edge-mock">
            <line x1="40%" y1="30%" x2="30%" y2="60%" stroke="var(--border-strong)" stroke-width="2" />
            <line x1="40%" y1="30%" x2="60%" y2="50%" stroke="var(--border-strong)" stroke-width="2" />
          </svg>
          
          <div class="canvas-hint">
            <i class="fa-solid fa-circle-nodes"></i>
            <p>图谱渲染引擎加载中... (即将接入 G6 / ECharts 渲染)</p>
            <small>提示：点击画布任意区域可模拟选中节点</small>
          </div>
        </div>
      </main>

      <!-- 右侧面板：节点详情 -->
      <aside class="kg-sidebar-right" :class="{ 'is-open': showDetails }">
        <div class="kg-details-header">
          <h3>节点详情</h3>
          <button class="icon-btn" @click.stop="closeDetails"><i class="fa-solid fa-xmark"></i></button>
        </div>
        
        <div v-if="activeNode" class="kg-details-content">
          <div class="node-header">
            <div class="node-icon" :class="activeNode.typeClass"><i class="fa-solid fa-file-code"></i></div>
            <div class="node-title">
              <h4>{{ activeNode.name }}</h4>
              <span class="badge">{{ activeNode.type }}</span>
            </div>
          </div>
          
          <div class="details-section">
            <h5>属性 (Properties)</h5>
            <div class="prop-grid">
              <div v-for="(val, key) in activeNode.properties" :key="key" class="prop-item">
                <span class="prop-key">{{ key }}</span>
                <span class="prop-val">{{ val }}</span>
              </div>
            </div>
          </div>
          
          <div class="details-section">
            <h5>相邻关系 (1 级)</h5>
            <ul class="relation-list">
              <li v-for="(rel, index) in activeNode.relations" :key="index">
                <span class="rel-tag">{{ rel.type }}</span> <span class="rel-target">{{ rel.target }}</span>
              </li>
            </ul>
          </div>
          
          <div class="details-actions">
            <button class="primary-btn full-btn">展开子节点</button>
            <button class="secondary-btn full-btn">设为起点</button>
          </div>
        </div>
        <div v-else class="kg-details-empty">
          <i class="fa-solid fa-hand-pointer"></i>
          <p>请在左侧图谱中点击实体节点</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.kg-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px 24px;
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

.kg-container {
  flex: 1;
  display: flex;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  overflow: hidden;
  position: relative;
}

.kg-sidebar-left {
  width: 240px;
  border-right: 1px solid var(--border);
  background: var(--surface-soft);
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  flex-shrink: 0;
}

.kg-sidebar-header {
  padding: 0 16px 8px;
}

.kg-sidebar-header h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mt-4 {
  margin-top: 24px;
}

.kg-entity-list,
.kg-relation-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.kg-entity-list li,
.kg-relation-list li {
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.kg-entity-list li:hover,
.kg-relation-list li:hover {
  background: var(--surface-muted);
}

.kg-entity-list li.active {
  background: var(--surface-strong);
  font-weight: 600;
}

.color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.color-dot.page { background: #3b82f6; }
.color-dot.component { background: #10b981; }
.color-dot.api { background: #f59e0b; }
.color-dot.testcase { background: #8b5cf6; }
.color-dot.bug { background: #ef4444; }

.kg-entity-list .count {
  margin-left: auto;
  font-size: 12px;
  color: var(--muted);
  background: var(--surface-muted);
  padding: 2px 6px;
  border-radius: 999px;
}

.kg-relation-list i {
  color: var(--muted);
  font-size: 12px;
}

.kg-canvas-area {
  flex: 1;
  position: relative;
  background: var(--surface-strong);
  overflow: hidden;
}

.kg-canvas-toolbar {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px;
  z-index: 10;
  box-shadow: var(--shadow-soft);
}

.kg-canvas-placeholder {
  width: 100%;
  height: 100%;
  position: relative;
  cursor: grab;
}

.canvas-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: var(--muted);
  pointer-events: none;
}

.canvas-hint i {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.3;
}

.canvas-hint p {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 500;
}

.kg-node-mock {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transform: translate(-50%, -50%);
  cursor: pointer;
  z-index: 5;
}

.node-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--surface);
  border: 3px solid;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transition: transform 0.2s;
}

.node-circle.page { border-color: #3b82f6; }
.node-circle.api { border-color: #f59e0b; }
.node-circle.testcase { border-color: #8b5cf6; }

.node-circle.is-selected {
  box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.05), 0 4px 12px rgba(0,0,0,0.15);
  transform: scale(1.15);
}

.kg-node-mock:hover .node-circle {
  transform: scale(1.15);
}

.kg-node-mock span {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  background: var(--surface);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  white-space: nowrap;
}

.kg-edge-mock {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.kg-sidebar-right {
  width: 320px;
  border-left: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 20;
}

.kg-sidebar-right.is-open {
  transform: translateX(0);
  box-shadow: -4px 0 24px rgba(0,0,0,0.05);
}

.kg-details-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kg-details-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.kg-details-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.node-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--surface-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.node-icon.page { color: #3b82f6; background: rgba(59, 130, 246, 0.1); }
.node-icon.api { color: #f59e0b; background: rgba(245, 158, 11, 0.1); }
.node-icon.testcase { color: #8b5cf6; background: rgba(139, 92, 246, 0.1); }

.node-title h4 {
  margin: 0 0 4px;
  font-size: 16px;
}

.node-title .badge {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--border-strong);
  border-radius: 4px;
}

.details-section h5 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--muted);
}

.prop-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--surface-muted);
  padding: 12px;
  border-radius: 8px;
}

.prop-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.prop-key {
  color: var(--muted);
}

.prop-val {
  font-weight: 500;
  color: var(--text);
}

.relation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relation-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}

.rel-tag {
  font-size: 10px;
  background: var(--surface-strong);
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  color: var(--muted);
}

.details-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: auto;
}

.kg-details-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  gap: 12px;
}

.kg-details-empty i {
  font-size: 32px;
  opacity: 0.5;
}

.full-btn {
  width: 100%;
  justify-content: center;
}
</style>
