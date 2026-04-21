<script setup lang="ts">
import type { SettingsPluginDefinition } from "../plugins";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();
</script>

<template>
  <section class="settings-pane">
    <div class="settings-pane-head">
      <div>
        <h3>存储设置</h3>
        <p>此设置页面正在开发中，暂无实际功能，仅用作占位展示。</p>
      </div>
    </div>

    <div class="settings-empty" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 300px; color: var(--muted);">
      <i class="fa-solid fa-person-digging" style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;"></i>
      <p style="font-size: 16px; font-weight: 500;">模块开发中...</p>
    </div>
  </section>
</template>