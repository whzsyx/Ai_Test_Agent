<script setup lang="ts">
import { useSessionStore } from "../../../stores/session";

const sessionStore = useSessionStore();
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <h3 class="section-title">当前后端已注册 Agent / Tool</h3>
      <p class="head-desc">列出通过 WebSocket 或 REST 接口注册到本系统的远端代理与工具链服务。</p>
    </div>
    <div class="registry-strip" v-if="sessionStore.agents.length || sessionStore.tools.length">
      <div class="registry-tags">
        <span v-for="agent in sessionStore.agents" :key="agent.key" class="registry-tag">{{ agent.name }}</span>
        <span v-for="tool in sessionStore.tools" :key="tool.key" class="registry-tag light">{{ tool.name }}</span>
      </div>
    </div>
    <div v-else class="registry-empty">
      <i class="fa-solid fa-ghost"></i>
      <p>当前暂无已注册的 Agent 或外部工具服务，请检查后端引擎状态。</p>
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