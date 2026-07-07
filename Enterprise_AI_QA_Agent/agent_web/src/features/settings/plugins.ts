import { markRaw, type Component } from "vue";

import EmailSettingsPlugin from "./plugins/EmailSettingsPlugin.vue";
import MailboxSettingsPlugin from "./plugins/MailboxSettingsPlugin.vue";
import GeneralSettingsPlugin from "./plugins/GeneralSettingsPlugin.vue";
import ModelSettingsPlugin from "./plugins/ModelSettingsPlugin.vue";
import PlatformSettingsPlugin from "./plugins/PlatformSettingsPlugin.vue";
import ChannelSettingsPlugin from "./plugins/ChannelSettingsPlugin.vue";
import StorageSettingsPlugin from "./plugins/StorageSettingsPlugin.vue";
import AboutSystemPlugin from "./plugins/AboutSystemPlugin.vue";
import { t } from "../../services/i18n";

export type SettingsPluginKey = "general" | "model" | "email" | "mailbox" | "platform" | "channel" | "storage" | "about";

export interface SettingsPluginDefinition {
  key: SettingsPluginKey;
  labelKey: string;
  summary: string;
  reserved?: boolean;
  component: Component;
  get label(): string;
}

function makePlugin(def: { key: SettingsPluginKey; labelKey: string; summary: string; reserved?: boolean; component: Component }): SettingsPluginDefinition {
  return {
    ...def,
    get label() {
      return t(def.labelKey);
    },
  };
}

export const settingsPlugins: SettingsPluginDefinition[] = [
  makePlugin({
    key: "general",
    labelKey: "settings.general",
    summary: "管理语言、通知、字体与数据管理偏好",
    component: markRaw(GeneralSettingsPlugin),
  }),
  makePlugin({
    key: "model",
    labelKey: "settings.models",
    summary: "管理大模型配置与当前主用模型",
    component: markRaw(ModelSettingsPlugin),
  }),
  makePlugin({
    key: "email",
    labelKey: "settings.email",
    summary: "配置邮件投递通道与 SMTP 能力",
    component: markRaw(EmailSettingsPlugin),
  }),
  makePlugin({
    key: "mailbox",
    labelKey: "settings.mailbox",
    summary: "配置 Agent Mailbox 信箱平台与收发能力",
    component: markRaw(MailboxSettingsPlugin),
  }),
  makePlugin({
    key: "platform",
    labelKey: "settings.integrations",
    summary: "统一管理第三方平台和外部能力接入",
    component: markRaw(PlatformSettingsPlugin),
  }),
  makePlugin({
    key: "channel",
    labelKey: "settings.channels",
    summary: "预留通知与协作通道的统一配置入口",
    component: markRaw(ChannelSettingsPlugin),
  }),
  makePlugin({
    key: "storage",
    labelKey: "settings.storage",
    summary: "预留对象存储与文件归档的统一配置入口",
    component: markRaw(StorageSettingsPlugin),
  }),
  makePlugin({
    key: "about",
    labelKey: "settings.about",
    summary: "查看系统介绍、技术栈、开源信息与反馈入口",
    component: markRaw(AboutSystemPlugin),
  }),
];
