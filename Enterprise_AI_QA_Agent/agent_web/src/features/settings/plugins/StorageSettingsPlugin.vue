<script setup lang="ts">
import type { SettingsPluginDefinition } from "../plugins";
import { t } from "../../../services/i18n";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();
</script>

<template>
  <section class="settings-pane">
    <div class="settings-pane-head">
      <div>
        <h3>{{ t("storage.title") }}</h3>
        <p>{{ t("storage.desc") }}</p>
      </div>
    </div>

    <div class="settings-empty" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 300px; color: var(--muted);">
      <i class="fa-solid fa-person-digging" style="font-size: 48px; margin-bottom: 16px; opacity: 0.5;"></i>
      <p style="font-size: 16px; font-weight: 500;">{{ t("storage.developing") }}</p>
    </div>
  </section>
</template>