import { markRaw, type Component } from "vue";

import SkillsPlugin from "./plugins/SkillsPlugin.vue";
import ApiDocsPlugin from "./plugins/ApiDocsPlugin.vue";
import ScannersPlugin from "./plugins/ScannersPlugin.vue";
import RegistryPlugin from "./plugins/RegistryPlugin.vue";
import PluginsPlugin from "./plugins/PluginsPlugin.vue";

export type ToolsPluginKey = "skills" | "apidocs" | "scanners" | "registry" | "plugins";

export interface ToolsPluginDefinition {
  key: ToolsPluginKey;
  labelKey: string;
  icon: string;
  iconType: string;
  component: Component;
}

export const toolsPlugins: ToolsPluginDefinition[] = [
  {
    key: "skills",
    labelKey: "tools.skills",
    icon: "fa-book-journal-whills",
    iconType: "solid",
    component: markRaw(SkillsPlugin),
  },
  {
    key: "apidocs",
    labelKey: "tools.apidocs",
    icon: "fa-file-code",
    iconType: "solid",
    component: markRaw(ApiDocsPlugin),
  },
  {
    key: "scanners",
    labelKey: "tools.scanners",
    icon: "fa-shield-halved",
    iconType: "solid",
    component: markRaw(ScannersPlugin),
  },
  {
    key: "registry",
    labelKey: "tools.registry",
    icon: "fa-server",
    iconType: "solid",
    component: markRaw(RegistryPlugin),
  },
  {
    key: "plugins",
    labelKey: "tools.plugins",
    icon: "fa-puzzle-piece",
    iconType: "solid",
    component: markRaw(PluginsPlugin),
  },
];
