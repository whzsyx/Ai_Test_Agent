import { markRaw, type Component } from "vue";

import SkillsPlugin from "./plugins/SkillsPlugin.vue";
import ApiDocsPlugin from "./plugins/ApiDocsPlugin.vue";
import ScannersPlugin from "./plugins/ScannersPlugin.vue";
import RegistryPlugin from "./plugins/RegistryPlugin.vue";
import PluginsPlugin from "./plugins/PluginsPlugin.vue";

export type ToolsPluginKey = "skills" | "apidocs" | "scanners" | "registry" | "plugins";

export interface ToolsPluginDefinition {
  key: ToolsPluginKey;
  label: string;
  icon: string;
  iconType: string;
  component: Component;
}

export const toolsPlugins: ToolsPluginDefinition[] = [
  {
    key: "skills",
    label: "增强技能 (Skills)",
    icon: "fa-book-journal-whills",
    iconType: "solid",
    component: markRaw(SkillsPlugin),
  },
  {
    key: "apidocs",
    label: "API 接口文档",
    icon: "fa-file-code",
    iconType: "solid",
    component: markRaw(ApiDocsPlugin),
  },
  {
    key: "scanners",
    label: "安全扫描引擎",
    icon: "fa-shield-halved",
    iconType: "solid",
    component: markRaw(ScannersPlugin),
  },
  {
    key: "registry",
    label: "后端注册服务",
    icon: "fa-server",
    iconType: "solid",
    component: markRaw(RegistryPlugin),
  },
  {
    key: "plugins",
    label: "插件导入",
    icon: "fa-puzzle-piece",
    iconType: "solid",
    component: markRaw(PluginsPlugin),
  },
];
