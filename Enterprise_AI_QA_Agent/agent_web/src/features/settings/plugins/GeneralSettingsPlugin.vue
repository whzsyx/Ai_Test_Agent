<script setup lang="ts">
import { computed, ref } from "vue";
import { NSelect, NSlider } from "naive-ui";

import { useGeneralSettingsStore, type AppFontFamily, type AppFontSize, type GeneralSettingsSnapshot } from "../../../stores/generalSettings";
import type { SettingsPluginDefinition } from "../plugins";

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

const modelLanguageOptions = [
  { value: "follow-system", label: "跟随系统语言" },
  ...languageOptions,
];

const fontFamilyOptions: Array<{ value: AppFontFamily; label: string; detail: string }> = [
  { value: "system", label: "系统默认", detail: "保持当前界面节奏，兼容多数设备。" },
  { value: "sans", label: "现代无衬线", detail: "更具现代感的英文字体优先。" },
  { value: "chinese", label: "中文优先", detail: "优先使用中文显示字体，适合长文阅读。" },
  { value: "serif", label: "传统衬线", detail: "传统优雅，适合沉浸式阅读。" },
  { value: "mono", label: "等宽调试", detail: "更适合日志、接口、代码和运行时信息。" },
];

const fontSizeOptions: Array<{ value: AppFontSize; label: string; detail: string }> = [
  { value: "small", label: "偏小", detail: "适合小屏幕设备，获取最高信息密度。" },
  { value: "compact", label: "紧凑", detail: "信息密度更高，行距更窄。" },
  { value: "standard", label: "标准", detail: "默认的均衡字号与行距。" },
  { value: "comfortable", label: "舒适", detail: "阅读距离更宽松，减轻视觉疲劳。" },
  { value: "large", label: "偏大", detail: "重点信息更突出，适合远距离阅读。" },
];

const fontFamilyMarks = {
  0: "系统",
  1: "无衬线",
  2: "中文",
  3: "衬线",
  4: "等宽",
};

const fontSizeMarks = {
  0: "偏小",
  1: "紧凑",
  2: "标准",
  3: "舒适",
  4: "偏大",
};

const dataActions = [
  {
    key: "backup",
    icon: "fa-solid fa-box-archive",
    title: "备份会话数据",
    detail: "导出会话、事件、快照、工具产物索引与用户设置。",
  },
  {
    key: "import",
    icon: "fa-solid fa-file-import",
    title: "导入备份",
    detail: "从备份包恢复会话数据，后续会先校验版本与完整性。",
  },
  {
    key: "cleanup",
    icon: "fa-solid fa-broom",
    title: "清理会话数据",
    detail: "按时间范围清理历史数据，真实执行前会加 dry-run 和二次确认。",
  },
] as const;

const fontFamilyIndex = computed({
  get() {
    return Math.max(
      0,
      fontFamilyOptions.findIndex((item) => item.value === draft.value.fontFamily),
    );
  },
  set(value: number) {
    draft.value.fontFamily = fontFamilyOptions[Math.round(value)]?.value ?? "system";
  },
});

const fontSizeIndex = computed({
  get() {
    return Math.max(
      0,
      fontSizeOptions.findIndex((item) => item.value === draft.value.fontSize),
    );
  },
  set(value: number) {
    draft.value.fontSize = fontSizeOptions[Math.round(value)]?.value ?? "standard";
  },
});

const permissionLabel = computed(() => {
  const permission = settingsStore.notificationPermissionStatus;
  if (permission === "granted") {
    return "桌面通知已授权";
  }
  if (permission === "denied") {
    return "浏览器已拒绝通知";
  }
  if (permission === "default") {
    return "等待申请通知权限";
  }
  return "当前浏览器不支持";
});

const languageLabel = computed(() => {
  return languageOptions.find((item) => item.value === draft.value.language)?.label ?? draft.value.language;
});

const modelOutputLanguageLabel = computed(() => {
  return (
    modelLanguageOptions.find((item) => item.value === draft.value.modelOutputLanguage)?.label ??
    draft.value.modelOutputLanguage
  );
});

const fontFamilyLabel = computed(() => {
  return fontFamilyOptions.find((item) => item.value === draft.value.fontFamily)?.label ?? "系统默认";
});

const fontSizeLabel = computed(() => {
  return fontSizeOptions.find((item) => item.value === draft.value.fontSize)?.label ?? "标准";
});

const fontLabel = computed(() => `${fontFamilyLabel.value} / ${fontSizeLabel.value}`);

const lastSavedLabel = computed(() => {
  if (!settingsStore.lastSavedAt) {
    return "尚未保存";
  }
  return new Intl.DateTimeFormat("zh-CN", {
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
  notice.value = "通用设置已保存，并已动态应用到当前工作台。";
}

function resetSettings() {
  settingsStore.resetGeneralSettings();
  syncDraftFromStore();
  notice.value = "已恢复默认通用设置。";
}

async function requestNotificationPermission() {
  const permission = await settingsStore.requestNotificationPermission();
  if (permission === "granted") {
    notice.value = "桌面通知权限已开启，后续可接入会话完成与审批提醒。";
  } else if (permission === "denied") {
    notice.value = "浏览器已拒绝桌面通知，需要在浏览器站点权限中手动开启。";
  } else if (permission === "unsupported") {
    notice.value = "当前浏览器环境不支持桌面通知。";
  } else {
    notice.value = "桌面通知权限暂未开启。";
  }
}

function markDataActionPlanned(title: string) {
  notice.value = `${title} 已预留按钮，明天接入后端数据管理接口时再启用真实操作。`;
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
          <h1 class="general-title">通用设置</h1>
          <p class="general-desc">
            统一管理系统语言、模型输出语言、桌面通知、字体体验与数据管理入口。
          </p>
        </div>
      </div>
    
    </header>

    <div class="general-meta">
      <div class="meta-item">
        <span class="meta-label">系统语言</span>
        <span class="meta-value">{{ languageLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">模型输出</span>
        <span class="meta-value">{{ modelOutputLanguageLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">通知状态</span>
        <span class="meta-value">{{ permissionLabel }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">字体方案</span>
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
          <h2 class="section-title">系统语言设置</h2>
          <p class="section-desc">拆分为系统本身的界面语言，以及后续注入模型请求的大模型输出语言。</p>
        </div>
        <div class="list-container">
          <div class="list-item">
            <div class="list-item__icon"><i class="fa-solid fa-language"></i></div>
            <div class="list-item__content">
              <label class="select-field">
                <div class="field-header">
                  <h3>系统本身语言</h3>
                  <p>后续接入 i18n 后，会用于切换工作台所有文案。</p>
                </div>
                <n-select
                  v-model:value="draft.language"
                  filterable
                  size="large"
                  :options="languageOptions"
                  placeholder="选择系统界面语言"
                />
              </label>
            </div>
          </div>
          <div class="list-item">
            <div class="list-item__icon"><i class="fa-solid fa-robot"></i></div>
            <div class="list-item__content">
              <label class="select-field">
                <div class="field-header">
                  <h3>大模型输出语言</h3>
                  <p>后续会写入模型调用上下文，例如“请默认使用中文回答”。</p>
                </div>
                <n-select
                  v-model:value="draft.modelOutputLanguage"
                  filterable
                  size="large"
                  :options="modelLanguageOptions"
                  placeholder="选择模型默认输出语言"
                />
              </label>
            </div>
          </div>
        </div>
      </section>

      <section class="general-section">
        <div class="section-header">
          <h2 class="section-title">通知设置</h2>
          <p class="section-desc">当用户不在当前界面时，用桌面通知兜住会话完成和审批待处理这两类关键事件。</p>
          <button type="button" class="action-btn" @click="requestNotificationPermission">
            <i class="fa-regular fa-bell"></i>
            <span>申请桌面通知权限</span>
          </button>
        </div>
        <div class="list-container">
          <label class="list-item switch-item">
            <div class="list-item__icon"><i class="fa-solid fa-check-double"></i></div>
            <div class="list-item__content">
              <h3>会话完成提醒</h3>
              <p>会话完成但不在当前界面时弹窗提醒。</p>
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
              <h3>审批待处理提醒</h3>
              <p>任务需审批但不在当前界面时弹窗提醒。</p>
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
              <h3>仅离开当前界面时提醒</h3>
              <p>避免用户正在操作当前会话时重复弹窗。</p>
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
          <h2 class="section-title">字体设置</h2>
          <p class="section-desc">配置界面字体方案与字号密度，满足不同工作场景需求。</p>
        </div>
        <div class="list-container">
          <div class="list-item slider-item">
            <div class="list-item__icon"><i class="fa-solid fa-font"></i></div>
            <div class="list-item__content">
              <div class="slider-field">
                <div class="slider-field__head">
                  <h3>字体方案</h3>
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
                  <h3>界面字号</h3>
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
              <span class="meta-label">效果预览</span>
            </div>
            <strong class="preview-text">御策天检正在编排一次可靠的 QA 运行时。</strong>
            <code>runtime.trace_id = "general-settings"</code>
          </div>

          <label class="list-item switch-item">
            <div class="list-item__icon"><i class="fa-solid fa-person-running"></i></div>
            <div class="list-item__content">
              <h3>减少动态效果</h3>
              <p>全局降低动画和过渡，适合长时间工作或低性能设备。</p>
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
          <h2 class="section-title">数据管理设置</h2>
          <p class="section-desc">当前预留按钮入口。后续版本将接入后端数据管理接口，包含二次确认与快照备份。</p>
        </div>
        <div class="list-container">
          <button
            v-for="item in dataActions"
            :key="item.key"
            type="button"
            class="list-item action-list-item"
            @click="markDataActionPlanned(item.title)"
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
        <h3>{{ isDirty ? "有未保存修改" : "设置已同步" }}</h3>
        <p>当前先保存到浏览器本地，后续会切换为后端用户设置接口。</p>
      </div>
      <div class="footer-actions">
        <button type="button" class="action-btn" @click="resetSettings">
          <i class="fa-solid fa-rotate-left"></i>
          <span>恢复默认</span>
        </button>
        <button type="button" class="action-btn primary" :disabled="!isDirty" @click="saveSettings">
          <i class="fa-solid fa-check"></i>
          <span>保存通用设置</span>
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
