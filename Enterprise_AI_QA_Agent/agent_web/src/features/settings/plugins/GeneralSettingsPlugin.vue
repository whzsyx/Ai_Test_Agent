<script setup lang="ts">
import { computed, ref } from "vue";
import { NSelect, NSlider } from "naive-ui";

import { useGeneralSettingsStore, type AppFontFamily, type AppFontSize, type GeneralSettingsSnapshot } from "../../../stores/generalSettings";
import type { SettingsPluginDefinition } from "../plugins";
import { t } from "../../../services/i18n";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();

const settingsStore = useGeneralSettingsStore();
const notice = ref("");
const draft = ref<GeneralSettingsSnapshot>({ ...settingsStore.settingsSnapshot });

const languageOptions = [
  { value: "zh-CN", label: "简体中文" },
  { value: "zh-TW", label: "繁體中文" },
  { value: "en-US", label: "English" },
  { value: "ja-JP", label: "日本語" },
  { value: "ko-KR", label: "한국어" },
  { value: "fr-FR", label: "Français" },
  { value: "de-DE", label: "Deutsch" },
  { value: "es-ES", label: "Español" },
  { value: "pt-BR", label: "Português" },
  { value: "ru-RU", label: "Русский" },
  { value: "ar-SA", label: "العربية" },
  { value: "hi-IN", label: "हिन्दी" },
  { value: "id-ID", label: "Bahasa Indonesia" },
  { value: "vi-VN", label: "Tiếng Việt" },
  { value: "th-TH", label: "ไทย" },
];

const modelLanguageOptions = computed(() => [
  { value: "follow-system", label: t("settings.follow_system_language") },
  ...languageOptions,
]);

const fontFamilyOptions = computed<Array<{ value: AppFontFamily; label: string; detail: string }>>(() => [
  { value: "system", label: t("settings.font_family_system"), detail: t("settings.font_family_system_desc") },
  { value: "sans", label: t("settings.font_family_sans"), detail: t("settings.font_family_sans_desc") },
  { value: "chinese", label: t("settings.font_family_chinese"), detail: t("settings.font_family_chinese_desc") },
  { value: "serif", label: t("settings.font_family_serif"), detail: t("settings.font_family_serif_desc") },
  { value: "mono", label: t("settings.font_family_mono"), detail: t("settings.font_family_mono_desc") },
]);

const fontSizeOptions = computed<Array<{ value: AppFontSize; label: string; detail: string }>>(() => [
  { value: "small", label: t("settings.font_size_small"), detail: t("settings.font_size_small_desc") },
  { value: "compact", label: t("settings.font_size_compact"), detail: t("settings.font_size_compact_desc") },
  { value: "standard", label: t("settings.font_size_standard"), detail: t("settings.font_size_standard_desc") },
  { value: "comfortable", label: t("settings.font_size_comfortable"), detail: t("settings.font_size_comfortable_desc") },
  { value: "large", label: t("settings.font_size_large"), detail: t("settings.font_size_large_desc") },
]);

const fontFamilyMarks = computed(() => ({
  0: t("settings.font_family_system"),
  1: t("settings.font_family_sans"),
  2: t("settings.font_family_chinese"),
  3: t("settings.font_family_serif"),
  4: t("settings.font_family_mono"),
}));

const fontSizeMarks = computed(() => ({
  0: t("settings.font_size_small"),
  1: t("settings.font_size_compact"),
  2: t("settings.font_size_standard"),
  3: t("settings.font_size_comfortable"),
  4: t("settings.font_size_large"),
}));

const dataActions = computed(() => [
  {
    key: "backup",
    icon: "fa-solid fa-box-archive",
    title: t("settings.data_backup"),
    detail: t("settings.data_backup_desc"),
  },
  {
    key: "import",
    icon: "fa-solid fa-file-import",
    title: t("settings.data_import"),
    detail: t("settings.data_import_desc"),
  },
  {
    key: "cleanup",
    icon: "fa-solid fa-broom",
    title: t("settings.data_cleanup"),
    detail: t("settings.data_cleanup_desc"),
  },
]);

const fontFamilyIndex = computed({
  get() {
    return Math.max(
      0,
      fontFamilyOptions.value.findIndex((item) => item.value === draft.value.fontFamily),
    );
  },
  set(value: number) {
    draft.value.fontFamily = fontFamilyOptions.value[Math.round(value)]?.value ?? "system";
  },
});

const fontSizeIndex = computed({
  get() {
    return Math.max(
      0,
      fontSizeOptions.value.findIndex((item) => item.value === draft.value.fontSize),
    );
  },
  set(value: number) {
    draft.value.fontSize = fontSizeOptions.value[Math.round(value)]?.value ?? "standard";
  },
});

const permissionLabel = computed(() => {
  const permission = settingsStore.notificationPermissionStatus;
  if (permission === "granted") {
    return t("settings.notify_granted");
  }
  if (permission === "denied") {
    return t("settings.notify_denied");
  }
  if (permission === "default") {
    return t("settings.notify_default");
  }
  return t("settings.notify_unsupported");
});

const languageLabel = computed(() => {
  return languageOptions.find((item) => item.value === draft.value.language)?.label ?? draft.value.language;
});

const modelOutputLanguageLabel = computed(() => {
    return (
    modelLanguageOptions.value.find((item) => item.value === draft.value.modelOutputLanguage)?.label ??
    draft.value.modelOutputLanguage
  );
});

const fontFamilyLabel = computed(() => {
  return fontFamilyOptions.value.find((item) => item.value === draft.value.fontFamily)?.label ?? t("settings.font_family_system");
});

const fontSizeLabel = computed(() => {
  return fontSizeOptions.value.find((item) => item.value === draft.value.fontSize)?.label ?? t("settings.font_size_standard");
});

const fontLabel = computed(() => `${fontFamilyLabel.value} / ${fontSizeLabel.value}`);

const lastSavedLabel = computed(() => {
  if (!settingsStore.lastSavedAt) {
    return t("settings.not_saved_yet");
  }
  return new Intl.DateTimeFormat(draft.value.language || "zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(settingsStore.lastSavedAt));
});

const isDirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(settingsStore.settingsSnapshot));

function syncDraftFromStore() {
  draft.value = { ...settingsStore.settingsSnapshot };
}

function saveSettings() {
  settingsStore.saveGeneralSettings(draft.value);
  syncDraftFromStore();
  notice.value = t("settings.saved");
}

function resetSettings() {
  settingsStore.resetGeneralSettings();
  syncDraftFromStore();
  notice.value = t("settings.reset_done");
}

async function requestNotificationPermission() {
  const permission = await settingsStore.requestNotificationPermission();
  if (permission === "granted") {
    notice.value = t("settings.notify_granted_message");
  } else if (permission === "denied") {
    notice.value = t("settings.notify_denied_message");
  } else if (permission === "unsupported") {
    notice.value = t("settings.notify_unsupported_message");
  } else {
    notice.value = t("settings.notify_default_message");
  }
}

async function handleDataAction(key: string, title: string) {
  if (key === "backup") {
    try {
      const result = await import("../../../services/api").then(m => m.api.exportData());
      notice.value = String((result as Record<string, unknown>).summary || t("settings.action_backup_ready", { title }));
    } catch (error) {
      notice.value = t("settings.action_failed", { title, error: error instanceof Error ? error.message : "unknown error" });
    }
  } else if (key === "import") {
    try {
      const result = await import("../../../services/api").then(m => m.api.importData());
      notice.value = String((result as Record<string, unknown>).summary || t("settings.action_import_soon", { title }));
    } catch (error) {
      notice.value = t("settings.action_failed", { title, error: error instanceof Error ? error.message : "unknown error" });
    }
  } else if (key === "cleanup") {
    try {
      const result = await import("../../../services/api").then(m =>
        m.api.cleanupData({ action: "cleanup", dry_run: true, time_range_days: 30 })
      );
      const summary = String((result as Record<string, unknown>).summary || "");
      const affectedCount = Number((result as Record<string, unknown>).affected_count || 0);
      notice.value = t("settings.action_cleanup_preview", {
        title,
        summary: summary || `${affectedCount}`,
      });
    } catch (error) {
      notice.value = t("settings.action_failed", { title, error: error instanceof Error ? error.message : "unknown error" });
    }
  } else {
    notice.value = t("settings.action_coming_soon", { title });
  }
}
</script>

<template>
  <section class="general-settings">
    <header class="general-header">
      <div class="general-header__main">
        <div class="general-logo">
          <i class="fa-solid fa-sliders"></i>
        </div>
        <div class="general-title-wrapper">
          <div class="general-eyebrow">Workspace Preferences</div>
          <h1 class="general-title">{{ t("settings.general") }}</h1>
          <p class="general-desc">
            {{ t("settings.language_desc") }}
          </p>
        </div>
      </div>
    
    </header>

    <div class="general-meta">
      <div class="meta-item">
        <span class="meta-label">{{ t("settings.system_language") }}</span>
        <span class="meta-value">{{ languageLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t("settings.model_language") }}</span>
        <span class="meta-value">{{ modelOutputLanguageLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t("settings.notify_title") }}</span>
        <span class="meta-value">{{ permissionLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">{{ t("settings.font_family") }}</span>
        <span class="meta-value">{{ fontLabel }}</span>
      </div>
    </div>

    <div v-if="notice" class="general-notice">
      <i class="fa-solid fa-circle-info"></i>
      <span>{{ notice }}</span>
    </div>

    <div class="general-sections">
      <section class="general-section">
        <div class="section-header">
          <h2 class="section-title">{{ t("settings.language_title") }}</h2>
          <p class="section-desc">{{ t("settings.language_desc") }}</p>
        </div>
        <div class="list-container">
          <div class="list-item">
            <div class="list-item__icon"><i class="fa-solid fa-language"></i></div>
            <div class="list-item__content">
              <label class="select-field">
                <div class="field-header">
                  <h3>{{ t("settings.system_language") }}</h3>
                  <p>{{ t("settings.system_language_desc") }}</p>
                </div>
                <n-select
                  v-model:value="draft.language"
                  filterable
                  size="large"
                  :options="languageOptions"
                  placeholder=""
                />
              </label>
            </div>
          </div>
          <div class="list-item">
            <div class="list-item__icon"><i class="fa-solid fa-robot"></i></div>
            <div class="list-item__content">
              <label class="select-field">
                <div class="field-header">
                  <h3>{{ t("settings.model_language") }}</h3>
                  <p>{{ t("settings.model_language_desc") }}</p>
                </div>
                <n-select
                  v-model:value="draft.modelOutputLanguage"
                  filterable
                  size="large"
                  :options="modelLanguageOptions"
                  placeholder=""
                />
              </label>
            </div>
          </div>
        </div>
      </section>

      <section class="general-section">
        <div class="section-header">
          <h2 class="section-title">{{ t("settings.notify_title") }}</h2>
          <p class="section-desc">{{ t("settings.notify_desc") }}</p>
          <button type="button" class="action-btn" @click="requestNotificationPermission">
            <i class="fa-regular fa-bell"></i>
            <span>{{ t("settings.notify_request_permission") }}</span>
          </button>
        </div>
        <div class="list-container">
          <label class="list-item switch-item">
            <div class="list-item__icon"><i class="fa-solid fa-check-double"></i></div>
            <div class="list-item__content">
              <h3>{{ t("settings.notify_session_complete") }}</h3>
              <p>{{ t("settings.notify_session_complete_desc") }}</p>
            </div>
            <div class="list-item__action">
              <div class="switch-wrapper">
                <input v-model="draft.notifySessionCompleteWhenAway" type="checkbox" />
                <span class="switch-visual"></span>
              </div>
            </div>
          </label>
          <label class="list-item switch-item">
            <div class="list-item__icon"><i class="fa-solid fa-clipboard-check"></i></div>
            <div class="list-item__content">
              <h3>{{ t("settings.notify_approval") }}</h3>
              <p>{{ t("settings.notify_approval_desc") }}</p>
            </div>
            <div class="list-item__action">
              <div class="switch-wrapper">
                <input v-model="draft.notifyApprovalRequiredWhenAway" type="checkbox" />
                <span class="switch-visual"></span>
              </div>
            </div>
          </label>
          <label class="list-item switch-item">
            <div class="list-item__icon"><i class="fa-solid fa-eye-slash"></i></div>
            <div class="list-item__content">
              <h3>{{ t("settings.notify_away_only") }}</h3>
              <p>{{ t("settings.notify_away_only_desc") }}</p>
            </div>
            <div class="list-item__action">
              <div class="switch-wrapper">
                <input v-model="draft.notificationsAwayOnly" type="checkbox" />
                <span class="switch-visual"></span>
              </div>
            </div>
          </label>
        </div>
      </section>

      <section class="general-section">
        <div class="section-header">
          <h2 class="section-title">{{ t("settings.font_title") }}</h2>
          <p class="section-desc">{{ t("settings.font_desc") }}</p>
        </div>
        <div class="list-container">
          <div class="list-item slider-item">
            <div class="list-item__icon"><i class="fa-solid fa-font"></i></div>
            <div class="list-item__content">
              <div class="slider-field">
                <div class="slider-field__head">
                  <h3>{{ t("settings.font_family") }}</h3>
                  <span class="meta-value">{{ fontFamilyLabel }}</span>
                </div>
                <p>{{ fontFamilyOptions[fontFamilyIndex]?.detail }}</p>
                <div class="slider-control">
                  <n-slider v-model:value="fontFamilyIndex" :min="0" :max="4" :step="1" :marks="fontFamilyMarks" :tooltip="false" />
                </div>
              </div>
            </div>
          </div>
          <div class="list-item slider-item">
            <div class="list-item__icon"><i class="fa-solid fa-text-height"></i></div>
            <div class="list-item__content">
              <div class="slider-field">
                <div class="slider-field__head">
                  <h3>{{ t("settings.font_size") }}</h3>
                  <span class="meta-value">{{ fontSizeLabel }}</span>
                </div>
                <p>{{ fontSizeOptions[fontSizeIndex]?.detail }}</p>
                <div class="slider-control">
                  <n-slider v-model:value="fontSizeIndex" :min="0" :max="4" :step="1" :marks="fontSizeMarks" :tooltip="false" />
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="list-container vertical" style="margin-top: 16px;">
          <div class="font-preview">
            <div class="font-preview__header">
              <i class="fa-solid fa-eye"></i>
              <span class="meta-label">{{ t("settings.font_preview") }}</span>
            </div>
            <strong class="preview-text">{{ t("settings.font_preview_text") }}</strong>
            <code>runtime.trace_id = "general-settings"</code>
          </div>

          <label class="list-item switch-item">
            <div class="list-item__icon"><i class="fa-solid fa-person-running"></i></div>
            <div class="list-item__content">
              <h3>{{ t("settings.reduce_motion") }}</h3>
              <p>{{ t("settings.reduce_motion_desc") }}</p>
            </div>
            <div class="list-item__action">
              <div class="switch-wrapper">
                <input v-model="draft.reduceMotion" type="checkbox" />
                <span class="switch-visual"></span>
              </div>
            </div>
          </label>
        </div>
      </section>

      <section class="general-section">
        <div class="section-header">
          <h2 class="section-title">{{ t("settings.data_title") }}</h2>
          <p class="section-desc">{{ t("settings.data_desc") }}</p>
        </div>
        <div class="list-container">
          <button
            v-for="item in dataActions"
            :key="item.key"
            type="button"
            class="list-item action-list-item"
            @click="handleDataAction(item.key, item.title)"
          >
            <div class="list-item__icon"><i :class="item.icon"></i></div>
            <div class="list-item__content">
              <h3>{{ item.title }}</h3>
              <p>{{ item.detail }}</p>
            </div>
            <div class="list-item__arrow">
              <i class="fa-solid fa-chevron-right"></i>
            </div>
          </button>
        </div>
      </section>
    </div>

    <footer class="general-footer">
      <div class="footer-info">
        <h3>{{ isDirty ? t("settings.unsaved") : t("settings.synced") }}</h3>
        <p>{{ t("settings.local_note") }}</p>
      </div>
      <div class="footer-actions">
        <button type="button" class="action-btn" @click="resetSettings">
          <i class="fa-solid fa-rotate-left"></i>
          <span>{{ t("settings.reset") }}</span>
        </button>
        <button type="button" class="action-btn primary" :disabled="!isDirty" @click="saveSettings">
          <i class="fa-solid fa-check"></i>
          <span>{{ t("settings.save") }}</span>
        </button>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.general-settings {
  /* Colors */
  --general-bg: #ffffff;
  --general-bg-subtle: #f8fafc;
  --general-bg-muted: #f1f5f9;
  --general-text-primary: #0f172a;
  --general-text-secondary: #475569;
  --general-text-tertiary: #64748b;
  --general-border: #e2e8f0;
  --general-border-hover: #cbd5e1;
  --general-accent: #111827;

  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 100%;
  color: var(--general-text-primary);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  padding: 8px 0 32px 0;
}

:global(:root[data-theme="dark"]) .general-settings {
  --general-bg: #0f172a;
  --general-bg-subtle: #1e293b;
  --general-bg-muted: #334155;
  --general-text-primary: #f8fafc;
  --general-text-secondary: #94a3b8;
  --general-text-tertiary: #64748b;
  --general-border: #1e293b;
  --general-border-hover: #334155;
  --general-accent: #f8fafc;
}

/* Header */
.general-header {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 24px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--general-border);
}

.general-header__main {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  flex: 1;
  min-width: 320px;
}

.general-logo {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--general-bg-muted);
  border: 1px solid var(--general-border);
  border-radius: 12px;
  font-size: 24px;
  color: var(--general-text-primary);
}


.general-title-wrapper {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.general-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--general-text-tertiary);
}

.general-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--general-text-primary);
  line-height: 1.2;
}

.general-desc {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--general-text-secondary);
  max-width: 600px;
}

.general-header__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.save-state {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 16px;
  background: var(--general-bg-subtle);
  border: 1px solid var(--general-border);
  border-radius: 8px;
  text-align: right;
}

.save-state__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--general-text-tertiary);
  text-transform: uppercase;
}

.save-state__value {
  font-size: 13px;
  font-weight: 600;
  color: var(--general-text-primary);
}

/* Meta Data */
.general-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 20px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--general-border);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--general-text-tertiary);
}

.meta-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--general-text-primary);
}

/* Notice */
.general-notice {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 10px;
  background: rgba(37, 99, 235, 0.06);
  color: #1d4ed8;
  font-size: 13px;
  line-height: 1.6;
}

:global(:root[data-theme="dark"]) .general-notice {
  color: #bfdbfe;
  background: rgba(37, 99, 235, 0.12);
}

/* Sections */
.general-sections {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.general-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--general-text-primary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.section-desc {
  margin: 0;
  font-size: 13px;
  color: var(--general-text-secondary);
  line-height: 1.6;
  max-width: 600px;
}

/* Action Button */
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--general-text-primary);
  background: var(--general-bg);
  border: 1px solid var(--general-border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover:not(:disabled) {
  background: var(--general-bg-subtle);
  border-color: var(--general-border-hover);
}

.action-btn.primary {
  background: var(--general-text-primary);
  color: var(--general-bg);
  border-color: var(--general-text-primary);
}

.action-btn.primary:hover:not(:disabled) {
  background: var(--general-text-secondary);
  border-color: var(--general-text-secondary);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* List Container */
.list-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.list-container.vertical {
  grid-template-columns: 1fr;
}

.list-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--general-border);
  border-radius: 12px;
  background: var(--general-bg);
  transition: border-color 0.2s ease;
}

.list-item:hover {
  border-color: var(--general-border-hover);
}

.list-item__icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--general-text-secondary);
  background: var(--general-bg-subtle);
  border-radius: 8px;
  font-size: 15px;
}

.list-item__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.list-item__content h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--general-text-primary);
}

.list-item__content p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--general-text-secondary);
}

.list-item__action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

/* Specific Items */
.action-list-item {
  cursor: pointer;
  text-align: left;
  align-items: center;
}

.list-item__arrow {
  color: var(--general-text-tertiary);
  font-size: 12px;
  transition: transform 0.2s ease;
}

.action-list-item:hover .list-item__arrow {
  transform: translateX(4px);
  color: var(--general-text-primary);
}

.switch-item {
  cursor: pointer;
  align-items: center;
}

/* Switch Wrapper */
.switch-wrapper {
  position: relative;
  width: 44px;
  height: 24px;
}

.switch-wrapper input {
  position: absolute;
  opacity: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
  z-index: 2;
  margin: 0;
}

.switch-visual {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 999px;
  background: var(--general-border-hover);
  transition: background-color 0.2s ease;
  pointer-events: none;
}

.switch-visual::after {
  content: "";
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s ease;
}

.switch-wrapper input:checked + .switch-visual {
  background: var(--general-text-primary);
}

.switch-wrapper input:checked + .switch-visual::after {
  transform: translateX(20px);
}

/* Fields */
.select-field {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.field-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--general-text-primary);
}

.field-header p {
  margin: 0;
  font-size: 13px;
  color: var(--general-text-secondary);
}

/* Slider Field */
.slider-item {
  flex-direction: row;
}

.slider-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.slider-field__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.slider-field__head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--general-text-primary);
}

.slider-control {
  margin-top: 16px;
  padding: 0 12px 12px;
}

/* Font Preview */
.font-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--general-border);
  border-radius: 12px;
  background: var(--general-bg-subtle);
  margin-top: 4px;
}

.font-preview__header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--general-text-tertiary);
}

.preview-text {
  font-size: calc(16px * var(--app-font-size-scale, 1));
  color: var(--general-text-primary);
  line-height: 1.5;
}

.font-preview code {
  width: fit-content;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--general-border);
  font-size: 12px;
  color: var(--general-text-secondary);
}

/* Footer */
.general-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding-top: 32px;
  border-top: 1px solid var(--general-border);
  flex-wrap: wrap;
}

.footer-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.footer-info h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--general-text-primary);
}

.footer-info p {
  margin: 0;
  font-size: 13px;
  color: var(--general-text-secondary);
}

.footer-actions {
  display: flex;
  gap: 12px;
}

/* Naive UI Overrides */
:deep(.n-slider) {
  --n-rail-height: 6px !important;
  --n-handle-size: 20px !important;
  --n-fill-color: var(--general-text-primary) !important;
  --n-fill-color-hover: var(--general-text-primary) !important;
  --n-handle-color: var(--general-bg) !important;
  --n-handle-border-color: var(--general-text-primary) !important;
  --n-handle-border-color-hover: var(--general-text-primary) !important;
  --n-handle-border-color-focus: var(--general-text-primary) !important;
  --n-handle-box-shadow-hover: 0 1px 4px rgba(0, 0, 0, 0.15) !important;
  --n-handle-box-shadow-active: 0 1px 4px rgba(0, 0, 0, 0.15) !important;
  --n-handle-box-shadow-focus: 0 0 0 3px rgba(15, 23, 42, 0.15) !important;
}

:global(:root[data-theme="dark"]) :deep(.n-slider) {
  --n-handle-box-shadow-focus: 0 0 0 3px rgba(248, 250, 252, 0.15) !important;
}

:deep(.n-slider-mark) {
  font-size: 13px;
  font-weight: 500;
  color: var(--general-text-tertiary);
  margin-top: 10px;
}

:deep(.n-slider-rail) {
  background: var(--general-bg-muted) !important;
}

:deep(.n-slider-handle-indicator) {
  font-size: 14px !important;
  padding: 6px 10px !important;
  border-radius: 8px !important;
  background-color: var(--general-text-primary) !important;
  color: var(--general-bg) !important;
  font-weight: 600 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
}

@media (max-width: 640px) {
  .general-header__main {
    flex-direction: column;
    align-items: flex-start;
  }

  .general-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .footer-actions {
    width: 100%;
  }

  .footer-actions button {
    flex: 1;
    justify-content: center;
  }
}
</style>
