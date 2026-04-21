<script setup lang="ts">
import { ref } from 'vue';

const activeTab = ref('all');
const activeDropdown = ref<string | null>(null);

const tabs = [
  { id: 'all', label: '全部任务' },
  { id: 'running', label: '运行中 (1)' },
  { id: 'queued', label: '排队中 (1)' },
  { id: 'completed', label: '已完成 (2)' }
];

function toggleDropdown(id: string) {
  if (activeDropdown.value === id) {
    activeDropdown.value = null;
  } else {
    activeDropdown.value = id;
  }
}

// Click outside to close dropdowns (simplified for demo)
function closeDropdowns() {
  activeDropdown.value = null;
}
</script>

<template>
  <section class="view-page task-page" @click="closeDropdowns">
    <header class="page-head">
      <div class="head-content">
        <h2>Task Pool</h2>
        <p class="head-desc">任务池与执行队列，支持批量管理与实时状态监控。</p>
      </div>
      <div class="head-actions">
        <div class="search-box">
          <i class="fa-solid fa-search"></i>
          <input type="text" placeholder="Search tasks by ID or name..." />
        </div>
        <button class="secondary-btn"><i class="fa-solid fa-stop"></i> 停止所有</button>
        <button class="primary-btn"><i class="fa-solid fa-play"></i> 运行选中</button>
      </div>
    </header>

    <div class="task-layout">
      <!-- 过滤器与统计 -->
      <div class="task-toolbar">
        <div class="task-tabs">
          <button 
            v-for="tab in tabs" 
            :key="tab.id"
            class="tab-btn" 
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>
        
        <div class="task-filters">
          <select class="filter-select">
            <option value="all">所有测试类型</option>
            <option value="single">单量执行</option>
            <option value="batch">批量执行</option>
            <option value="api">接口安全测试</option>
          </select>
          <select class="filter-select">
            <option value="all">所有模型</option>
            <option value="deepseek">DeepSeek-V3</option>
            <option value="gpt4o">GPT-4o</option>
          </select>
        </div>
      </div>

      <!-- 任务列表 -->
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-checkbox"><input type="checkbox" /></th>
              <th class="col-id">Case ID</th>
              <th class="col-name">任务名称 (Title)</th>
              <th class="col-type">测试类型</th>
              <th class="col-model">Agent / 模型</th>
              <th class="col-status">当前状态</th>
              <th class="col-actions align-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr class="row-active">
              <td class="col-checkbox"><input type="checkbox" /></td>
              <td class="col-id mono strong">CASE-1024</td>
              <td class="col-name strong">验证标准登录流程 (正常账号)</td>
              <td class="col-type"><span class="badge badge-gray">单量执行</span></td>
              <td class="col-model mono">DeepSeek-V3</td>
              <td class="col-status">
                <span class="status-indicator status-running">
                  <span class="pulse-dot"></span> 浏览器操作中
                </span>
              </td>
              <td class="col-actions align-right">
                <button class="action-btn danger" title="停止任务"><i class="fa-solid fa-stop"></i></button>
              </td>
            </tr>
            
            <tr>
              <td class="col-checkbox"><input type="checkbox" /></td>
              <td class="col-id mono strong">CASE-1025</td>
              <td class="col-name strong">登录异常输入边界 Fuzzing</td>
              <td class="col-type"><span class="badge badge-gray">批量执行</span></td>
              <td class="col-model mono text-muted">-</td>
              <td class="col-status">
                <span class="status-indicator status-queued">
                  <i class="fa-regular fa-clock"></i> 排队中
                </span>
              </td>
              <td class="col-actions align-right">
                <div class="dropdown-wrapper" @click.stop>
                  <button class="action-btn" title="更多选项" @click="toggleDropdown('task-2')"><i class="fa-solid fa-ellipsis-vertical"></i></button>
                  <div class="dropdown-menu" :class="{ show: activeDropdown === 'task-2' }">
                    <button class="dropdown-item"><i class="fa-regular fa-copy"></i> 克隆任务</button>
                    <button class="dropdown-item"><i class="fa-solid fa-code"></i> 查看配置详情</button>
                    <div class="dropdown-divider"></div>
                    <button class="dropdown-item danger"><i class="fa-regular fa-trash-can"></i> 删除任务</button>
                  </div>
                </div>
              </td>
            </tr>
            
            <tr>
              <td class="col-checkbox"><input type="checkbox" /></td>
              <td class="col-id mono strong">API-902</td>
              <td class="col-name strong">越权漏洞探测 (/api/admin/users)</td>
              <td class="col-type"><span class="badge badge-gray">接口安全测试</span></td>
              <td class="col-model mono">GPT-4o</td>
              <td class="col-status">
                <span class="status-indicator status-success">
                  <i class="fa-solid fa-check"></i> 已完成
                </span>
              </td>
              <td class="col-actions align-right">
                <div class="dropdown-wrapper" @click.stop>
                  <button class="action-btn" title="更多选项" @click="toggleDropdown('task-3')"><i class="fa-solid fa-ellipsis-vertical"></i></button>
                  <div class="dropdown-menu" :class="{ show: activeDropdown === 'task-3' }">
                    <button class="dropdown-item"><i class="fa-solid fa-rotate-right"></i> 重新运行</button>
                    <button class="dropdown-item"><i class="fa-regular fa-copy"></i> 克隆任务</button>
                    <button class="dropdown-item"><i class="fa-solid fa-code"></i> 查看配置详情</button>
                    <div class="dropdown-divider"></div>
                    <button class="dropdown-item danger"><i class="fa-regular fa-trash-can"></i> 删除任务</button>
                  </div>
                </div>
              </td>
            </tr>
            
            <tr class="row-error">
              <td class="col-checkbox"><input type="checkbox" /></td>
              <td class="col-id mono strong">CASE-1021</td>
              <td class="col-name strong">密码重置流程测试</td>
              <td class="col-type"><span class="badge badge-gray">单量执行</span></td>
              <td class="col-model mono">DeepSeek-V3</td>
              <td class="col-status">
                <span class="status-indicator status-error">
                  <i class="fa-solid fa-xmark"></i> 验证失败
                </span>
              </td>
              <td class="col-actions align-right">
                <div class="dropdown-wrapper" @click.stop>
                  <button class="action-btn" title="更多选项" @click="toggleDropdown('task-4')"><i class="fa-solid fa-ellipsis-vertical"></i></button>
                  <div class="dropdown-menu" :class="{ show: activeDropdown === 'task-4' }">
                    <button class="dropdown-item"><i class="fa-solid fa-rotate-right"></i> 重新运行</button>
                    <button class="dropdown-item"><i class="fa-regular fa-copy"></i> 克隆任务</button>
                    <button class="dropdown-item"><i class="fa-solid fa-code"></i> 查看配置详情</button>
                    <div class="dropdown-divider"></div>
                    <button class="dropdown-item danger"><i class="fa-regular fa-trash-can"></i> 删除任务</button>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.task-page {
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

.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-box i {
  position: absolute;
  left: 12px;
  color: var(--muted);
  font-size: 14px;
}

.search-box input {
  height: 36px;
  padding: 0 16px 0 36px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
  width: 240px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.search-box input:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.task-layout {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}

.task-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-soft);
}

.task-tabs {
  display: flex;
  gap: 4px;
  background: var(--surface-muted);
  padding: 4px;
  border-radius: 8px;
}

.tab-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  color: var(--text);
}

.tab-btn.active {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.task-filters {
  display: flex;
  gap: 12px;
}

.filter-select {
  height: 32px;
  padding: 0 32px 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%236b7280'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E") no-repeat right 8px center/16px;
  appearance: none;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
}

.filter-select:focus {
  outline: none;
  border-color: var(--blue);
}

.table-container {
  flex: 1;
  overflow: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.data-table th {
  position: sticky;
  top: 0;
  background: var(--surface);
  padding: 14px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  z-index: 10;
}

.data-table td {
  padding: 16px;
  font-size: 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  vertical-align: middle;
}

.data-table tbody tr {
  transition: background-color 0.2s ease;
}

.data-table tbody tr:hover {
  background: var(--surface-soft);
}

.data-table tbody tr.row-active {
  background: rgba(59, 130, 246, 0.02);
}

.data-table tbody tr.row-error {
  background: rgba(239, 68, 68, 0.02);
}

/* Columns */
.col-checkbox { width: 48px; text-align: center; }
.col-id { width: 140px; }
.col-name { min-width: 280px; }
.col-type { width: 160px; }
.col-model { width: 160px; }
.col-status { width: 180px; }
.col-actions { width: 100px; white-space: nowrap; }

.align-right { text-align: right; }
.mono { font-family: var(--font-mono, monospace); }
.strong { font-weight: 600; }
.text-muted { color: var(--muted); }

/* Badges & Status */
.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.badge-gray {
  background: var(--surface-muted);
  color: var(--muted);
  border: 1px solid var(--border);
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.status-running { color: #2563eb; }
.status-queued { color: #6b7280; }
.status-success { color: #16a34a; }
.status-error { color: #dc2626; }

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  position: relative;
}

.pulse-dot::after {
  content: '';
  position: absolute;
  top: -4px;
  left: -4px;
  right: -4px;
  bottom: -4px;
  border-radius: 50%;
  border: 2px solid #3b82f6;
  animation: pulse 1.5s infinite cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 0;
}

@keyframes pulse {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}

/* Actions */
.dropdown-wrapper {
  position: relative;
  display: inline-block;
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 160px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 10px 24px rgba(0,0,0,0.1);
  padding: 4px;
  display: flex;
  flex-direction: column;
  z-index: 100;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-8px);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.dropdown-menu.show {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.dropdown-item {
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: background-color 0.2s;
}

.dropdown-item i {
  color: var(--muted);
  font-size: 14px;
  width: 16px;
  text-align: center;
}

.dropdown-item:hover {
  background: var(--surface-muted);
}

.dropdown-item.danger {
  color: #dc2626;
}

.dropdown-item.danger i {
  color: #dc2626;
}

.dropdown-item.danger:hover {
  background: rgba(239, 68, 68, 0.05);
}

.dropdown-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}
</style>
