<script setup lang="ts">
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <h3 class="section-title">安全与系统探测器 (Scanners)</h3>
      <p class="head-desc">配置并查看内置与外部集成的安全扫描引擎，提供主动化的漏洞探测能力。</p>
    </div>
    <div class="scanner-grid">
      <article class="scanner-card">
        <i class="fa-solid fa-satellite-dish"></i>
        <span>Nuclei 引擎</span>
        <small>基于模板的快速漏洞扫描</small>
      </article>
      <article class="scanner-card">
        <i class="fa-solid fa-database"></i>
        <span>SQLMap 注入</span>
        <small>自动化 SQL 注入与探测</small>
      </article>
      <article class="scanner-card">
        <i class="fa-solid fa-bug"></i>
        <span>XSStrike 探测</span>
        <small>高级 XSS 跨站模糊测试</small>
      </article>
      <article class="scanner-card">
        <i class="fa-solid fa-bolt"></i>
        <span>定制 Fuzzing</span>
        <small>自动组装与注入 Payload</small>
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