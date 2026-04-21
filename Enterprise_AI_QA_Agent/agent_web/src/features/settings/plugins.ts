import { markRaw, type Component } from "vue";

import EmailSettingsPlugin from "./plugins/EmailSettingsPlugin.vue";
import ModelSettingsPlugin from "./plugins/ModelSettingsPlugin.vue";
import PlatformSettingsPlugin from "./plugins/PlatformSettingsPlugin.vue";
import ChannelSettingsPlugin from "./plugins/ChannelSettingsPlugin.vue";
import StorageSettingsPlugin from "./plugins/StorageSettingsPlugin.vue";

export type SettingsPluginKey = "model" | "email" | "platform" | "channel" | "storage";

export interface SettingsPluginDefinition {
  key: SettingsPluginKey;
  label: string;
  summary: string;
  reserved?: boolean;
  component: Component;
}

export const settingsPlugins: SettingsPluginDefinition[] = [
  {
    key: "model",
    label: "模型设置",
    summary: "管理大模型配置与主用模型",
    component: markRaw(ModelSettingsPlugin),
  },
  {
    key: "email",
    label: "邮件设置",
    summary: "配置邮件投递与 SMTP 能力",
    component: markRaw(EmailSettingsPlugin),
  },
  {
    key: "platform",
    label: "管理平台接入",
    summary: "预留插件入口",
    component: markRaw(PlatformSettingsPlugin),
  },
  {
    key: "channel",
    label: "通讯渠道设置",
    summary: "预留插件入口",
    component: markRaw(ChannelSettingsPlugin),
  },
  {
    key: "storage",
    label: "存储设置",
    summary: "预留插件入口",
    component: markRaw(StorageSettingsPlugin),
  },
];
