import { defineStore } from "pinia";

export type SystemLanguage = string;
export type ModelOutputLanguage = string;
export type AppFontFamily = "system" | "sans" | "chinese" | "serif" | "mono";
export type AppFontSize = "small" | "compact" | "standard" | "comfortable" | "large";
export type DesktopNotificationPermission = NotificationPermission | "unsupported";

export interface GeneralSettingsSnapshot {
  language: SystemLanguage;
  modelOutputLanguage: ModelOutputLanguage;
  notifySessionCompleteWhenAway: boolean;
  notifyApprovalRequiredWhenAway: boolean;
  notificationsAwayOnly: boolean;
  fontFamily: AppFontFamily;
  fontSize: AppFontSize;
  reduceMotion: boolean;
  lastSavedAt: string;
}

interface GeneralSettingsState extends GeneralSettingsSnapshot {
  notificationPermissionStatus: DesktopNotificationPermission;
}

const STORAGE_KEY = "enterprise-ai-qa-agent-general-settings";

const defaultSettings: GeneralSettingsSnapshot = {
  language: "zh-CN",
  modelOutputLanguage: "follow-system",
  notifySessionCompleteWhenAway: true,
  notifyApprovalRequiredWhenAway: true,
  notificationsAwayOnly: true,
  fontFamily: "system",
  fontSize: "standard",
  reduceMotion: false,
  lastSavedAt: "",
};

const fontFamilyMap: Record<AppFontFamily, string> = {
  system: 'Inter, "PingFang SC", "Microsoft YaHei", ui-sans-serif, system-ui, sans-serif',
  sans: 'Roboto, "Helvetica Neue", Helvetica, Arial, sans-serif',
  chinese: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", "LXGW WenKai", ui-sans-serif, system-ui, sans-serif',
  serif: '"Noto Serif CJK SC", "Noto Serif SC", SimSun, "Times New Roman", serif',
  mono: '"JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", "Microsoft YaHei", monospace',
};

const fontSizeScaleMap: Record<AppFontSize, string> = {
  small: "0.85",
  compact: "0.92",
  standard: "1",
  comfortable: "1.08",
  large: "1.18",
};

function isLanguageCode(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isAppFontFamily(value: unknown): value is AppFontFamily {
  return value === "system" || value === "sans" || value === "chinese" || value === "serif" || value === "mono";
}

function isAppFontSize(value: unknown): value is AppFontSize {
  return value === "small" || value === "compact" || value === "standard" || value === "comfortable" || value === "large";
}

function readDesktopPermission(): DesktopNotificationPermission {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "unsupported";
  }
  return window.Notification.permission;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function normalizeSettings(value: unknown): GeneralSettingsSnapshot {
  const record = asRecord(value);
  return {
    language: isLanguageCode(record.language) ? record.language : defaultSettings.language,
    modelOutputLanguage: isLanguageCode(record.modelOutputLanguage)
      ? record.modelOutputLanguage
      : defaultSettings.modelOutputLanguage,
    notifySessionCompleteWhenAway:
      typeof record.notifySessionCompleteWhenAway === "boolean"
        ? record.notifySessionCompleteWhenAway
        : defaultSettings.notifySessionCompleteWhenAway,
    notifyApprovalRequiredWhenAway:
      typeof record.notifyApprovalRequiredWhenAway === "boolean"
        ? record.notifyApprovalRequiredWhenAway
        : defaultSettings.notifyApprovalRequiredWhenAway,
    notificationsAwayOnly:
      typeof record.notificationsAwayOnly === "boolean" ? record.notificationsAwayOnly : defaultSettings.notificationsAwayOnly,
    fontFamily: isAppFontFamily(record.fontFamily) ? record.fontFamily : defaultSettings.fontFamily,
    fontSize: isAppFontSize(record.fontSize) ? record.fontSize : defaultSettings.fontSize,
    reduceMotion: typeof record.reduceMotion === "boolean" ? record.reduceMotion : defaultSettings.reduceMotion,
    lastSavedAt: typeof record.lastSavedAt === "string" ? record.lastSavedAt : defaultSettings.lastSavedAt,
  };
}

function persistSettings(settings: GeneralSettingsSnapshot) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function applySettingsToDocument(settings: GeneralSettingsSnapshot) {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  root.lang = settings.language;
  root.dataset.appLanguage = settings.language;
  root.dataset.modelOutputLanguage = settings.modelOutputLanguage;
  root.dataset.appFont = settings.fontFamily;
  root.dataset.reduceMotion = settings.reduceMotion ? "true" : "false";
  root.style.setProperty("--app-font-family", fontFamilyMap[settings.fontFamily]);
  root.style.setProperty("--app-font-size-scale", fontSizeScaleMap[settings.fontSize]);
}

export const useGeneralSettingsStore = defineStore("generalSettings", {
  state: (): GeneralSettingsState => ({
    ...defaultSettings,
    notificationPermissionStatus: readDesktopPermission(),
  }),
  getters: {
    hasDesktopNotificationSupport(state): boolean {
      return state.notificationPermissionStatus !== "unsupported";
    },
    canSendDesktopNotifications(state): boolean {
      return state.notificationPermissionStatus === "granted";
    },
    settingsSnapshot(state): GeneralSettingsSnapshot {
      return normalizeSettings(state);
    },
  },
  actions: {
    hydrateGeneralSettings() {
      let nextSettings = { ...defaultSettings };

      if (typeof window !== "undefined") {
        const savedSettings = window.localStorage.getItem(STORAGE_KEY);
        if (savedSettings) {
          try {
            nextSettings = normalizeSettings(JSON.parse(savedSettings));
          } catch {
            nextSettings = { ...defaultSettings };
          }
        }
      }

      this.$patch({
        ...nextSettings,
        notificationPermissionStatus: readDesktopPermission(),
      });
      applySettingsToDocument(nextSettings);
    },
    saveGeneralSettings(patch: Partial<GeneralSettingsSnapshot>) {
      const nextSettings = normalizeSettings({
        ...this.settingsSnapshot,
        ...patch,
        lastSavedAt: new Date().toISOString(),
      });
      this.$patch(nextSettings);
      persistSettings(nextSettings);
      applySettingsToDocument(nextSettings);
    },
    resetGeneralSettings() {
      const nextSettings = normalizeSettings({
        ...defaultSettings,
        lastSavedAt: new Date().toISOString(),
      });
      this.$patch(nextSettings);
      persistSettings(nextSettings);
      applySettingsToDocument(nextSettings);
    },
    async requestNotificationPermission(): Promise<DesktopNotificationPermission> {
      if (typeof window === "undefined" || !("Notification" in window)) {
        this.notificationPermissionStatus = "unsupported";
        return "unsupported";
      }

      const permission = await window.Notification.requestPermission();
      this.notificationPermissionStatus = permission;
      return permission;
    },
  },
});
