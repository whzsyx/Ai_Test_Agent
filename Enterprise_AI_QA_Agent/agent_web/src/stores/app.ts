import { defineStore } from "pinia";

import { api } from "../services/api";
import { t } from "../services/i18n";
import type {
  AgentDescriptor,
  HealthResponse,
  ServiceCheckItem,
  ServiceCheckStatus,
  SystemStatusSummary,
  ToolDescriptor,
} from "../types";

function buildCheck(
  key: string,
  label: string,
  status: ServiceCheckStatus,
  detail: string,
  meta?: string,
): ServiceCheckItem {
  return { key, label, status, detail, meta };
}

type ThemeMode = "light" | "dark";

const THEME_STORAGE_KEY = "enterprise-ai-qa-agent-theme";

function applyThemeToDocument(theme: ThemeMode) {
  document.documentElement.dataset.theme = theme;
  document.body.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function isOnlineMemoryBackend(memoryBackend: string) {
  return memoryBackend === "qdrant" || memoryBackend.startsWith("postgres");
}

function isUnavailableMemoryBackend(memoryBackend: string) {
  return memoryBackend.endsWith("_unavailable");
}

export const useAppStore = defineStore("app", {
  state: () => ({
    health: null as HealthResponse | null,
    agents: null as AgentDescriptor[] | null,
    tools: null as ToolDescriptor[] | null,
    loading: false,
    error: "",
    lastCheckedAt: "" as string,
    theme: "light" as ThemeMode,
  }),
  getters: {
    systemStatus(state): SystemStatusSummary {
      const checks: ServiceCheckItem[] = [];
      const backendOnline = state.health?.status === "ok";
      const memoryBackend = state.health?.memory_backend ?? "unknown";
      const sessionBackend = state.health?.session_backend ?? "unknown";
      const toolJobBackend = state.health?.tool_job_backend ?? "unknown";
      const uiGraphBackend = state.health?.ui_graph_backend ?? "unknown";
      const knowledgeEnabled = state.health?.knowledge_enabled ?? false;
      const memoryTarget = state.health?.memory_target ?? "";
      const knowledgeTarget = state.health?.knowledge_target ?? "";

      checks.push(
        backendOnline
          ? buildCheck(
              "backend",
              t("status.backend"),
              "online",
              t("status.backend_online", { env: state.health?.environment ?? "unknown" }),
              state.health?.name ?? "API",
            )
          : buildCheck("backend", t("status.backend"), "offline", t("status.backend_offline")),
      );

      checks.push(
        Array.isArray(state.agents)
          ? state.agents.length > 0
            ? buildCheck(
                "agents",
                t("status.agents"),
                "online",
                t("status.agents_online", { count: state.agents.length }),
                `${state.agents.length} agents`,
              )
            : buildCheck("agents", t("status.agents"), "degraded", t("status.agents_degraded"))
          : buildCheck("agents", t("status.agents"), "offline", t("status.agents_offline")),
      );

      checks.push(
        Array.isArray(state.tools)
          ? state.tools.length > 0
            ? buildCheck(
                "tools",
                t("status.tools"),
                "online",
                t("status.tools_online", { count: state.tools.length }),
                `${state.tools.length} tools`,
              )
            : buildCheck("tools", t("status.tools"), "degraded", t("status.tools_degraded"))
          : buildCheck("tools", t("status.tools"), "offline", t("status.tools_offline")),
      );

      if (!backendOnline) {
        checks.push(buildCheck("knowledge", t("status.knowledge"), "offline", t("status.knowledge_offline_backend")));
      } else if (!knowledgeEnabled) {
        checks.push(
          buildCheck("knowledge", t("status.knowledge"), "offline", t("status.knowledge_disabled"), "disabled"),
        );
      } else if (isOnlineMemoryBackend(memoryBackend)) {
        checks.push(
          buildCheck(
            "knowledge",
            t("status.knowledge"),
            "online",
            t("status.knowledge_online", { memoryBackend, uiGraphBackend }),
            memoryTarget || knowledgeTarget || `${sessionBackend} / ${toolJobBackend}`,
          ),
        );
      } else if (isUnavailableMemoryBackend(memoryBackend)) {
        checks.push(
          buildCheck(
            "knowledge",
            t("status.knowledge"),
            "offline",
            t("status.knowledge_unavailable", { memoryBackend }),
            memoryTarget || knowledgeTarget || memoryBackend,
          ),
        );
      } else if (memoryBackend === "local_memory") {
        checks.push(
          buildCheck(
            "knowledge",
            t("status.knowledge"),
            "offline",
            t("status.knowledge_local_memory"),
            "local_memory",
          ),
        );
      } else {
        checks.push(
          buildCheck("knowledge", t("status.knowledge"), "offline", t("status.knowledge_unknown"), memoryBackend),
        );
      }

      const totalCount = checks.length;
      const onlineCount = checks.filter((check) => check.status === "online").length;
      const hasOffline = checks.some((check) => check.status === "offline");
      const hasDegraded = checks.some((check) => check.status === "degraded");
      const tone: ServiceCheckStatus = hasOffline ? "offline" : hasDegraded ? "degraded" : "online";
      const label =
        tone === "online"
          ? t("status.ready")
          : tone === "degraded"
            ? t("status.partial")
            : t("status.offline");

      return {
        label,
        tone,
        checks,
        onlineCount,
        totalCount,
      };
    },
  },
  actions: {
    hydrateTheme() {
      const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
      const nextTheme: ThemeMode = savedTheme === "dark" ? "dark" : "light";
      this.theme = nextTheme;
      applyThemeToDocument(nextTheme);
    },
    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      window.localStorage.setItem(THEME_STORAGE_KEY, this.theme);
      applyThemeToDocument(this.theme);
    },
    async fetchSystemStatus() {
      this.loading = true;
      this.error = "";

      const [healthResult, agentsResult, toolsResult] = await Promise.allSettled([
        api.getHealth(),
        api.listAgents(),
        api.listTools(),
      ]);

      if (healthResult.status === "fulfilled") {
        this.health = healthResult.value;
      } else {
        this.health = null;
      }

      if (agentsResult.status === "fulfilled") {
        this.agents = agentsResult.value;
      } else {
        this.agents = null;
      }

      if (toolsResult.status === "fulfilled") {
        this.tools = toolsResult.value;
      } else {
        this.tools = null;
      }

      const failedMessages = [healthResult, agentsResult, toolsResult]
        .filter((result): result is PromiseRejectedResult => result.status === "rejected")
        .map((result) => {
          const reason = result.reason;
          return reason instanceof Error ? reason.message : String(reason);
        })
        .filter(Boolean);

      this.error = failedMessages[0] ?? "";
      this.lastCheckedAt = new Date().toISOString();
      this.loading = false;
    },
  },
});
