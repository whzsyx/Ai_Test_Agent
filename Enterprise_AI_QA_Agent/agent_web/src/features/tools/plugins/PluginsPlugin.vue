<script setup lang="ts">
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <h3 class="section-title">插件导入 (Plugins)</h3>
      <p class="head-desc">导入并管理第三方插件以扩展平台功能。</p>
    </div>
    <div class="plugins-empty">
      <i class="fa-solid fa-puzzle-piece"></i>
      <p>暂无可用插件，请点击上方按钮导入或安装新插件。</p>
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

.plugins-empty {
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

.plugins-empty i {
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