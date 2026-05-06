import { markRaw, type Component } from "vue";

import EmailSettingsPlugin from "./plugins/EmailSettingsPlugin.vue";
import ModelSettingsPlugin from "./plugins/ModelSettingsPlugin.vue";
import PlatformSettingsPlugin from "./plugins/PlatformSettingsPlugin.vue";
import ChannelSettingsPlugin from "./plugins/ChannelSettingsPlugin.vue";
import StorageSettingsPlugin from "./plugins/StorageSettingsPlugin.vue";
import AboutSystemPlugin from "./plugins/AboutSystemPlugin.vue";

export type SettingsPluginKey = "model" | "email" | "platform" | "channel" | "storage" | "about";

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
    summary: "管理大模型配置与当前主用模型",
    component: markRaw(ModelSettingsPlugin),
  },
  {
    key: "email",
    label: "邮件设置",
    summary: "配置邮件投递通道与 SMTP 能力",
    component: markRaw(EmailSettingsPlugin),
  },
  {
    key: "platform",
    label: "管理平台接入",
    summary: "统一管理第三方平台和外部能力接入",
    component: markRaw(PlatformSettingsPlugin),
  },
  {
    key: "channel",
    label: "通讯渠道设置",
    summary: "预留通知与协作通道的统一配置入口",
    component: markRaw(ChannelSettingsPlugin),
  },
  {
    key: "storage",
    label: "存储设置",
    summary: "预留对象存储与文件归档的统一配置入口",
    component: markRaw(StorageSettingsPlugin),
  },
  {
    key: "about",
    label: "关于系统",
    summary: "查看系统介绍、技术栈、开源信息与反馈入口",
    component: markRaw(AboutSystemPlugin),
  },
];
