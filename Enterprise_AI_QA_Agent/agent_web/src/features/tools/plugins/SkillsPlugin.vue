<script setup lang="ts">
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <h3 class="section-title">已安装 Skills (程序化指导知识)</h3>
      <p class="head-desc">Skills 是 Markdown 格式的指令集，执行时将作为“便签”注入到 LLM 系统提示词中，增强 Agent 的专业能力。</p>
    </div>
    <div class="skills-grid">
      <article class="skill-card">
        <div class="skill-icon"><i class="fa-brands fa-markdown"></i></div>
        <div class="skill-body">
          <div class="skill-head">
            <h4>webapp-testing-guidelines</h4>
            <span class="skill-state enabled">已启用</span>
          </div>
          <p>提供 Web 表单、弹窗交互、瞬态 UI 处理的标准测试规范。</p>
          <div class="mono muted-small">Source: anthropics/webapp-testing</div>
        </div>
      </article>

      <article class="skill-card dimmed">
        <div class="skill-icon"><i class="fa-brands fa-markdown"></i></div>
        <div class="skill-body">
          <div class="skill-head">
            <h4>api-security-fuzzing</h4>
            <span class="skill-state disabled">已禁用</span>
          </div>
          <p>提供 API 安全测试的负载生成指导，包括认证绕过、SQLi 和 XSS 样式探针。</p>
          <div class="mono muted-small">Source: 本地上传 (MinIO)</div>
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