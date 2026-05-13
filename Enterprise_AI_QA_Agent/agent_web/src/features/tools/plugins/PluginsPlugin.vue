<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useMessage } from "naive-ui";

import { api } from "../../../services/api";
import { t } from "../../../services/i18n";
import type {
  IntegrationCreateRequest,
  IntegrationKind,
  IntegrationRecord,
  IntegrationTestResponse,
  IntegrationTransport,
  ManagedMCPServerDescriptor,
  ManagedMCPToolDescriptor,
  MCPProviderDescriptor,
} from "../../../types";

type PluginTab = "api" | "mcp" | "managed";
type MCPPresetMode = "manual" | "json";

interface RawMcpJsonConfig {
  command?: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, unknown>;
  headers?: Record<string, unknown>;
  url?: string;
  endpoint_url?: string;
  transport?: string;
  type?: string;
  description?: string;
  capabilities?: string[];
  enabled?: boolean;
}

const toast = useMessage();

const integrations = ref<IntegrationRecord[]>([]);
const managedMcpServers = ref<ManagedMCPServerDescriptor[]>([]);
const mcpProviders = ref<MCPProviderDescriptor[]>([]);
const mcpToolsByServer = ref<Record<string, ManagedMCPToolDescriptor[]>>({});

const loading = ref(false);
const error = ref("");
const saving = ref(false);
const deletingId = ref("");
const testingId = ref("");
const managedTestingKey = ref("");
const toolsLoadingKey = ref("");
const managedToolsModalOpen = ref(false);
const managedToolsModalKey = ref<string | null>(null);

const modalOpen = ref(false);
const editingId = ref<string | null>(null);
const testResult = ref<IntegrationTestResponse | null>(null);
const activeTab = ref<PluginTab>("api");

const formKind = ref<IntegrationKind>("api");
const formName = ref("");
const formEnabled = ref(true);
const formDescription = ref("");
const formProjectName = ref("");
const formDocumentUrl = ref("");

const formTransport = ref<IntegrationTransport>("http");
const formEndpointUrl = ref("");
const formCommand = ref("");
const formCapabilities = ref("");
const formHeadersJson = ref("{}");
const formHeadersLines = ref("");
const formEnvJson = ref("{}");

const formBaseUrl = ref("");
const formAuthType = ref<"none" | "bearer" | "api_key" | "basic">("none");
const formAuthToken = ref("");
const formApiKeyHeader = ref("X-API-Key");
const formUsername = ref("");
const formPassword = ref("");

const mcpCreateMode = ref<MCPPresetMode>("manual");
const mcpJsonPlaceholder = `{
  "mcpServers": {
    "postman-mcp": {
      "url": "https://mcp.postman.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}`;
const mcpJsonText = ref("");
const mcpAdvancedOpen = ref(false);
const apiAdvancedOpen = ref(false);

const mcpIntegrations = computed(() => integrations.value.filter((item) => item.kind === "mcp"));
const apiIntegrations = computed(() => integrations.value.filter((item) => item.kind === "api"));
const providerSummary = computed(() =>
  mcpProviders.value.map((provider) => ({
    key: provider.key,
    label: `${provider.name}${provider.supports_document_import ? ` · ${t("plugins.supports_doc_import")}` : ""}`,
  })),
);

const canUseJsonImport = computed(() => formKind.value === "mcp" && !editingId.value);

const managedToolsModalTitle = computed(() => {
  const key = managedToolsModalKey.value;
  if (!key) return t("plugins.mcp_tools");
  return managedMcpServers.value.find((s) => s.key === key)?.name ?? key;
});

const managedToolsModalTools = computed(() => {
  const key = managedToolsModalKey.value;
  if (!key) return [];
  return mcpToolsByServer.value[key] ?? [];
});

function resetForm(kind: IntegrationKind = "api") {
  formKind.value = kind;
  formName.value = "";
  formEnabled.value = true;
  formDescription.value = "";
  formProjectName.value = "";
  formDocumentUrl.value = "";
  formTransport.value = "http";
  formEndpointUrl.value = "";
  formCommand.value = "";
  formCapabilities.value = "";
  formHeadersJson.value = "{}";
  formHeadersLines.value = "";
  formEnvJson.value = "{}";
  formBaseUrl.value = "";
  formAuthType.value = "none";
  formAuthToken.value = "";
  formApiKeyHeader.value = "X-API-Key";
  formUsername.value = "";
  formPassword.value = "";
  testResult.value = null;
  mcpCreateMode.value = "manual";
  mcpJsonText.value = "";
  mcpAdvancedOpen.value = false;
  apiAdvancedOpen.value = false;
}

function openCreate(kind: IntegrationKind = "api") {
  editingId.value = null;
  resetForm(kind);
  modalOpen.value = true;
}

function closeModal() {
  modalOpen.value = false;
  editingId.value = null;
  error.value = "";
  resetForm("api");
}

function parseJsonMap(label: string, raw: string): Record<string, string> {
  const trimmed = raw.trim();
  if (!trimmed) {
    return {};
  }

  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${label} ${t("plugins.must_be_json_object")}`);
    }

    return normalizeUnknownMap(parsed);
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : `${label} ${t("plugins.parse_failed")}`);
  }
}

function parseHeaderLines(raw: string): Record<string, string> {
  const trimmed = raw.trim();
  if (!trimmed) {
    return {};
  }

  const result: Record<string, string> = {};
  const lines = trimmed.split(/\r?\n/);
  for (const line of lines) {
    const normalized = line.trim();
    if (!normalized) {
      continue;
    }
    const separatorIndex = normalized.indexOf(":");
    if (separatorIndex <= 0) {
      throw new Error(`${t("plugins.header_format_error")}${normalized}`);
    }
    const key = normalized.slice(0, separatorIndex).trim();
    const value = normalized.slice(separatorIndex + 1).trim();
    if (!key || !value) {
      throw new Error(`${t("plugins.header_format_error")}${normalized}`);
    }
    result[key] = value;
  }
  return result;
}

function normalizeUnknownMap(value: Record<string, unknown> | undefined | null): Record<string, string> {
  const result: Record<string, string> = {};
  if (!value) {
    return result;
  }

  Object.entries(value).forEach(([key, item]) => {
    const normalizedKey = String(key || "").trim();
    const normalizedValue = String(item ?? "").trim();
    if (normalizedKey && normalizedValue) {
      result[normalizedKey] = normalizedValue;
    }
  });
  return result;
}

function toCapabilities() {
  return formCapabilities.value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildPayload(): IntegrationCreateRequest {
  const headers =
    formKind.value === "mcp" && mcpCreateMode.value === "manual"
      ? parseHeaderLines(formHeadersLines.value)
      : parseJsonMap(t("plugins.label_headers"), formHeadersJson.value);
  const env = parseJsonMap(t("plugins.label_env"), formEnvJson.value);
  const payload: IntegrationCreateRequest = {
    name: formName.value.trim(),
    kind: formKind.value,
    enabled: formEnabled.value,
    description: formDescription.value.trim() || null,
    project_name: formProjectName.value.trim() || null,
    document_url: formDocumentUrl.value.trim() || null,
    headers,
    env,
    capabilities: toCapabilities(),
    metadata: {},
  };

  if (formKind.value === "mcp") {
    payload.transport = formTransport.value;
    payload.endpoint_url = formEndpointUrl.value.trim() || null;
    payload.command = formCommand.value.trim() || null;
    payload.base_url = null;
    payload.auth_type = "none";
    payload.auth_config = {};
  } else {
    payload.base_url = formBaseUrl.value.trim() || null;
    payload.transport = null;
    payload.endpoint_url = null;
    payload.command = null;
    payload.auth_type = formAuthType.value;

    if (formAuthType.value === "bearer") {
      payload.auth_config = { token: formAuthToken.value.trim() };
    } else if (formAuthType.value === "api_key") {
      payload.auth_config = {
        header_name: formApiKeyHeader.value.trim() || "X-API-Key",
        token: formAuthToken.value.trim(),
      };
    } else if (formAuthType.value === "basic") {
      payload.auth_config = {
        username: formUsername.value.trim(),
        password: formPassword.value,
      };
    } else {
      payload.auth_config = {};
    }
  }

  if (!payload.name) {
    throw new Error(t("plugins.name_required"));
  }

  if (formKind.value === "mcp") {
    if (formTransport.value === "stdio" && !payload.command) {
      throw new Error(t("plugins.stdio_command_required"));
    }
    if (formTransport.value !== "stdio" && !payload.endpoint_url) {
      throw new Error(t("plugins.endpoint_url_required"));
    }
  } else if (!payload.base_url) {
    throw new Error(t("plugins.base_url_required"));
  }

  return payload;
}

function hydrateForm(record: IntegrationRecord) {
  formKind.value = record.kind;
  formName.value = record.name;
  formEnabled.value = record.enabled;
  formDescription.value = record.description || "";
  formProjectName.value = record.project_name || "";
  formDocumentUrl.value = record.document_url || "";
  formTransport.value = (record.transport || "http") as IntegrationTransport;
  formEndpointUrl.value = record.endpoint_url || "";
  formCommand.value = record.command || "";
  formCapabilities.value = record.capabilities.join(", ");
  formHeadersJson.value = JSON.stringify(record.headers || {}, null, 2);
  formHeadersLines.value = Object.entries(record.headers || {})
    .map(([key, value]) => `${key}: ${value}`)
    .join("\n");
  formEnvJson.value = JSON.stringify(record.env || {}, null, 2);
  formBaseUrl.value = record.base_url || "";
  formAuthType.value = record.auth_type;
  formAuthToken.value = record.auth_config.token || "";
  formApiKeyHeader.value = record.auth_config.header_name || "X-API-Key";
  formUsername.value = record.auth_config.username || "";
  formPassword.value = record.auth_config.password || "";
  mcpCreateMode.value = "manual";
}

function selectTransport(transport: IntegrationTransport) {
  formTransport.value = transport;
}

function commandWithArgs(command?: string, args?: string[]) {
  const normalizedCommand = String(command || "").trim();
  if (!normalizedCommand) {
    return "";
  }

  const normalizedArgs = Array.isArray(args)
    ? args
        .map((item) => String(item || "").trim())
        .filter(Boolean)
        .map((item) => (/\s/.test(item) ? JSON.stringify(item) : item))
    : [];

  return [normalizedCommand, ...normalizedArgs].join(" ").trim();
}

function normalizeJsonTransport(config: RawMcpJsonConfig): IntegrationTransport {
  const hint = String(config.transport || config.type || "").trim().toLowerCase();
  if (hint === "stdio") {
    return "stdio";
  }
  if (hint === "websocket" || hint === "ws" || hint === "wss") {
    return "websocket";
  }
  if (hint === "http" || hint === "streamable-http" || hint === "sse") {
    return "http";
  }
  if (config.command) {
    return "stdio";
  }
  return "http";
}

function extractJsonServerEntries(parsed: unknown): Array<[string, RawMcpJsonConfig]> {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(t("plugins.json_must_be_object"));
  }

  const root = parsed as Record<string, unknown>;
  if (root.mcpServers && typeof root.mcpServers === "object" && !Array.isArray(root.mcpServers)) {
    return Object.entries(root.mcpServers as Record<string, RawMcpJsonConfig>);
  }

  const looksLikeSingleServer =
    "command" in root || "url" in root || "endpoint_url" in root || "headers" in root || "args" in root;
  if (looksLikeSingleServer) {
    return [[String(root.name || "imported-mcp").trim() || "imported-mcp", root as RawMcpJsonConfig]];
  }

  const entries = Object.entries(root).filter(([, value]) => value && typeof value === "object" && !Array.isArray(value));
  if (entries.length) {
    return entries as Array<[string, RawMcpJsonConfig]>;
  }

  throw new Error(t("plugins.no_importable_config"));
}

function buildPayloadFromJsonEntry(name: string, config: RawMcpJsonConfig): IntegrationCreateRequest {
  const transport = normalizeJsonTransport(config);
  const command = commandWithArgs(config.command, config.args);
  const endpointUrl = String(config.endpoint_url || config.url || "").trim() || null;

  return {
    name: name.trim() || "imported-mcp",
    kind: "mcp",
    enabled: config.enabled ?? true,
    description: String(config.description || "").trim() || null,
    project_name: null,
    document_url: null,
    transport,
    endpoint_url: transport === "stdio" ? null : endpointUrl,
    command: transport === "stdio" ? (command || null) : null,
    capabilities: Array.isArray(config.capabilities)
      ? config.capabilities.map((item) => String(item || "").trim()).filter(Boolean)
      : [],
    headers: normalizeUnknownMap(config.headers || {}),
    env: normalizeUnknownMap(config.env || {}),
    base_url: null,
    auth_type: "none",
    auth_config: {},
    metadata: {
      imported_from: "mcp_json",
      cwd: String(config.cwd || "").trim() || null,
      original_args: Array.isArray(config.args) ? config.args : [],
    },
  };
}

async function importMcpFromJson() {
  saving.value = true;
  error.value = "";
  try {
    const rawJson = mcpJsonText.value.trim();
    if (!rawJson) {
      throw new Error(t("plugins.paste_json_first"));
    }
    const parsed = JSON.parse(rawJson) as unknown;
    const entries = extractJsonServerEntries(parsed);
    if (!entries.length) {
      throw new Error(t("plugins.no_importable_config"));
    }

    const created: IntegrationRecord[] = [];
    for (const [name, config] of entries) {
      const payload = buildPayloadFromJsonEntry(name, config);
      if (payload.transport === "stdio" && !payload.command) {
        throw new Error(`MCP ${name} ${t("plugins.missing_command_stdio")}`);
      }
      if (payload.transport !== "stdio" && !payload.endpoint_url) {
        throw new Error(`MCP ${name} ${t("plugins.missing_url")}`);
      }
      created.push(await api.createIntegration(payload));
    }

    integrations.value = [...created, ...integrations.value].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    await loadData();
    toast.success(`${t("plugins.imported_count", { count: String(created.length) })}`, { duration: 2200 });
    closeModal();
  } catch (err) {
    const detail = err instanceof Error ? err.message : t("plugins.json_import_failed");
    toast.error(detail);
  } finally {
    saving.value = false;
  }
}

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [integrationItems, managedItems, providerItems] = await Promise.all([
      api.listIntegrations(),
      api.listManagedMcpServers(),
      api.listMcpProviders(),
    ]);
    integrations.value = integrationItems;
    managedMcpServers.value = managedItems;
    mcpProviders.value = providerItems;
  } catch (err) {
    error.value = err instanceof Error ? err.message : t("plugins.load_failed");
  } finally {
    loading.value = false;
  }
}

function upsertIntegration(record: IntegrationRecord) {
  const index = integrations.value.findIndex((item) => item.id === record.id);
  if (index >= 0) {
    const next = [...integrations.value];
    next[index] = record;
    integrations.value = next.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return;
  }
  integrations.value = [record, ...integrations.value].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

function openEdit(record: IntegrationRecord) {
  editingId.value = record.id;
  hydrateForm(record);
  testResult.value = null;
  modalOpen.value = true;
}

async function saveIntegration() {
  saving.value = true;
  error.value = "";
  try {
    const payload = buildPayload();
    const saved = editingId.value
      ? await api.updateIntegration(editingId.value, payload)
      : await api.createIntegration(payload);
    upsertIntegration(saved);
    toast.success(editingId.value ? t("plugins.updated") : t("plugins.created"), { duration: 2200 });
    await loadData();
    closeModal();
  } catch (err) {
    const detail = err instanceof Error ? err.message : t("plugins.save_failed");
    toast.error(detail);
  } finally {
    saving.value = false;
  }
}

async function deleteIntegration(record: IntegrationRecord) {
  if (deletingId.value) {
    return;
  }
  deletingId.value = record.id;
  try {
    await api.deleteIntegration(record.id);
    integrations.value = integrations.value.filter((item) => item.id !== record.id);
    await loadData();
    toast.success(`${t("plugins.deleted")}: ${record.name}`, { duration: 2200 });
  } catch (err) {
    toast.error(err instanceof Error ? err.message : t("plugins.delete_failed"));
  } finally {
    deletingId.value = "";
  }
}

async function testIntegration(record: IntegrationRecord) {
  testingId.value = record.id;
  try {
    const result = await api.testIntegration(record.id);
    testResult.value = result;
    toast[result.ok ? "success" : "warning"](result.message, { duration: 2600 });
  } catch (err) {
    const detail = err instanceof Error ? err.message : t("plugins.test_failed");
    testResult.value = {
      ok: false,
      message: detail,
    };
    toast.error(detail);
  } finally {
    testingId.value = "";
  }
}

async function openManagedToolsModal(server: ManagedMCPServerDescriptor) {
  managedToolsModalKey.value = server.key;
  managedToolsModalOpen.value = true;
  if (mcpToolsByServer.value[server.key]) {
    return;
  }
  toolsLoadingKey.value = server.key;
  try {
    const response = await api.listManagedMcpTools(server.key);
    mcpToolsByServer.value = {
      ...mcpToolsByServer.value,
      [server.key]: response.tools,
    };
  } catch (err) {
    toast.error(err instanceof Error ? err.message : t("plugins.load_tools_failed"));
    closeManagedToolsModal();
  } finally {
    toolsLoadingKey.value = "";
  }
}

function closeManagedToolsModal() {
  managedToolsModalOpen.value = false;
  managedToolsModalKey.value = null;
}

async function testManagedServer(server: ManagedMCPServerDescriptor) {
  managedTestingKey.value = server.key;
  try {
    const result = await api.testManagedMcpServer(server.key);
    const meta = `tools ${result.tool_count ?? 0}${
      result.latency_ms != null ? ` · ${result.latency_ms} ms` : ""
    }`;
    const text = `${result.message} · ${meta}`;
    toast[result.ok ? "success" : "warning"](text, { duration: 3200 });
  } catch (err) {
    toast.error(err instanceof Error ? err.message : t("plugins.managed_test_failed"));
  } finally {
    managedTestingKey.value = "";
  }
}

function handleOpenCreateEvent(event: Event) {
  const detail = (event as CustomEvent<{ kind?: IntegrationKind }>).detail;
  const kind = detail?.kind || "api";
  activeTab.value = kind === "mcp" ? "mcp" : "api";
  openCreate(kind);
}

function broadcastPluginsIntegrationPane() {
  window.dispatchEvent(
    new CustomEvent("qa-agent:plugins-integration-pane", { detail: { tab: activeTab.value } }),
  );
}

watch(activeTab, broadcastPluginsIntegrationPane);

onMounted(() => {
  void loadData();
  broadcastPluginsIntegrationPane();
  window.addEventListener("qa-agent:open-integration-create", handleOpenCreateEvent as EventListener);
});

onBeforeUnmount(() => {
  window.removeEventListener("qa-agent:open-integration-create", handleOpenCreateEvent as EventListener);
});
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <div class="header-left">
        <h3 class="section-title">{{ t("plugins.title") }}</h3>
        <p class="head-desc">{{ t("plugins.desc") }}</p>
      </div>
    </div>

    <div class="main-tabs">
      <button :class="{ active: activeTab === 'api' }" @click="activeTab = 'api'">
        {{ t("plugins.tab_api") }} <span class="count">{{ apiIntegrations.length }}</span>
      </button>
      <button :class="{ active: activeTab === 'mcp' }" @click="activeTab = 'mcp'">
        {{ t("plugins.tab_mcp") }} <span class="count">{{ mcpIntegrations.length }}</span>
      </button>
      <button :class="{ active: activeTab === 'managed' }" @click="activeTab = 'managed'">
        {{ t("plugins.tab_managed") }} <span class="count">{{ managedMcpServers.length }}</span>
      </button>
    </div>

    <div v-if="loading" class="plugins-empty">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <p>{{ t("plugins.loading") }}</p>
    </div>
    <div v-else-if="error" class="plugins-empty plugins-empty--error">
      <i class="fa-solid fa-circle-exclamation"></i>
      <p>{{ error }}</p>
    </div>
    <template v-else>
      <section v-if="activeTab === 'api'" class="panel-section">
        <div v-if="apiIntegrations.length" class="integration-grid">
          <article v-for="item in apiIntegrations" :key="item.id" class="integration-card">
            <div class="integration-card-head">
              <div class="card-title-row">
                <span class="status-dot" :class="{ active: item.enabled }"></span>
                <h5>{{ item.name }}</h5>
              </div>
              <span class="meta-badge">{{ item.enabled ? t("plugins.enabled") : t("plugins.disabled") }}</span>
            </div>
            <p class="card-desc">{{ item.description || t("plugins.no_description") }}</p>
            <div class="integration-meta">
              <div class="meta-item"><i class="fa-solid fa-link"></i> {{ item.base_url || t("plugins.no_base_url") }}</div>
              <div class="meta-item"><i class="fa-solid fa-book"></i> {{ item.document_url || t("plugins.no_doc_url") }}</div>
              <div class="meta-item"><i class="fa-solid fa-key"></i> {{ item.auth_type }}</div>
              <div class="meta-item"><i class="fa-solid fa-folder"></i> {{ item.project_name || t("plugins.no_project") }}</div>
            </div>
            <div class="integration-actions">
              <button class="ghost-btn" @click="openEdit(item)">{{ t("common.edit") }}</button>
              <button class="ghost-btn" :disabled="testingId === item.id" @click="testIntegration(item)">
                {{ testingId === item.id ? t("plugins.testing") : t("plugins.test_connection") }}
              </button>
              <button class="ghost-btn danger" :disabled="deletingId === item.id" @click="deleteIntegration(item)">
                {{ deletingId === item.id ? t("plugins.deleting") : t("common.delete") }}
              </button>
            </div>
          </article>
        </div>
        <div v-else class="plugins-empty">
          <i class="fa-solid fa-cloud-slash"></i>
          <p>{{ t("plugins.no_api") }}</p>
        </div>
      </section>

      <section v-if="activeTab === 'mcp'" class="panel-section">
        <div v-if="mcpIntegrations.length" class="integration-grid">
          <article v-for="item in mcpIntegrations" :key="item.id" class="integration-card">
            <div class="integration-card-head">
              <div class="card-title-row">
                <span class="status-dot" :class="{ active: item.enabled }"></span>
                <h5>{{ item.name }}</h5>
              </div>
              <span class="meta-badge">{{ item.transport || "unknown" }}</span>
            </div>
            <p class="card-desc">{{ item.description || t("plugins.no_description") }}</p>
            <div class="integration-meta">
              <div class="meta-item"><i class="fa-solid fa-network-wired"></i> {{ item.endpoint_url || item.command || t("plugins.no_connection") }}</div>
              <div class="meta-item"><i class="fa-solid fa-book"></i> {{ item.document_url || t("plugins.no_doc_url") }}</div>
              <div class="meta-item"><i class="fa-solid fa-folder"></i> {{ item.project_name || t("plugins.no_project") }}</div>
              <div class="meta-item"><i class="fa-solid fa-screwdriver-wrench"></i> {{ item.capabilities.join(", ") || t("plugins.no_capabilities") }}</div>
            </div>
            <div class="integration-actions">
              <button class="ghost-btn" @click="openEdit(item)">{{ t("common.edit") }}</button>
              <button class="ghost-btn" :disabled="testingId === item.id" @click="testIntegration(item)">
                {{ testingId === item.id ? t("plugins.testing") : t("plugins.test_connection") }}
              </button>
              <button class="ghost-btn danger" :disabled="deletingId === item.id" @click="deleteIntegration(item)">
                {{ deletingId === item.id ? t("plugins.deleting") : t("common.delete") }}
              </button>
            </div>
          </article>
        </div>
        <div v-else class="plugins-empty">
          <i class="fa-solid fa-plug-circle-xmark"></i>
          <p>{{ t("plugins.no_mcp") }}</p>
        </div>
      </section>

      <section v-if="activeTab === 'managed'" class="panel-section">
        <div v-if="providerSummary.length" class="provider-strip">
          <span class="provider-chip" v-for="provider in providerSummary" :key="provider.key">{{ provider.label }}</span>
        </div>

        <div v-if="managedMcpServers.length" class="integration-grid">
          <article v-for="server in managedMcpServers" :key="server.key" class="integration-card integration-card--managed">
            <div class="integration-card-head">
              <div class="card-title-row">
                <span class="status-dot" :class="{ active: server.enabled }"></span>
                <h5>{{ server.name }}</h5>
              </div>
              <span class="meta-badge">{{ server.source_kind === "builtin" ? "builtin" : (server.provider_name || "external") }}</span>
            </div>
            <p class="card-desc">{{ server.summary }}</p>
            <div class="integration-meta">
              <div class="meta-item"><i class="fa-solid fa-shuffle"></i> {{ server.transport }}</div>
              <div class="meta-item"><i class="fa-solid fa-signal"></i> {{ server.status }}</div>
              <div class="meta-item"><i class="fa-solid fa-folder"></i> {{ server.project_name || t("plugins.no_project") }}</div>
              <div class="meta-item"><i class="fa-solid fa-book"></i> {{ server.endpoint_url || server.document_url || t("plugins.no_remote_url") }}</div>
            </div>
            <div class="tag-row">
              <span v-for="capability in server.capabilities" :key="capability">{{ capability }}</span>
              <span v-if="server.supports_document_import">supports-doc-import</span>
              <span v-if="server.supports_workspace_selection">supports-workspace</span>
            </div>

            <div class="managed-card-footer">
              <div class="managed-action-bar" role="group" :aria-label="t('plugins.mcp_actions')">
                <button
                  type="button"
                  class="managed-action-btn managed-action-btn--tools"
                  :disabled="toolsLoadingKey === server.key"
                  @click="openManagedToolsModal(server)"
                >
                  <i class="fa-solid fa-layer-group" aria-hidden="true"></i>
                  <span>{{ toolsLoadingKey === server.key ? t("plugins.loading_tools") : t("plugins.view_tools") }}</span>
                </button>
                <button
                  type="button"
                  class="managed-action-btn managed-action-btn--test"
                  :disabled="managedTestingKey === server.key"
                  @click="testManagedServer(server)"
                >
                  <i class="fa-solid fa-plug-circle-check" aria-hidden="true"></i>
                  <span>{{ managedTestingKey === server.key ? t("plugins.testing") : t("plugins.unified_test") }}</span>
                </button>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="plugins-empty">
          <i class="fa-solid fa-diagram-project"></i>
          <p>{{ t("plugins.no_managed") }}</p>
        </div>
      </section>
    </template>

    <div v-if="modalOpen" class="tools-modal-backdrop" @click.self="closeModal">
      <section class="tools-modal integration-modal">
        <header class="tools-modal-head">
          <div>
            <h3>{{ editingId ? t("plugins.edit_integration") : `${t("plugins.new_integration")} ${formKind === 'mcp' ? 'MCP' : 'API'}` }}</h3>
            <p v-if="formKind === 'mcp'"></p>
            <p v-else>{{ t("plugins.api_form_hint") }}</p>
          </div>
          <button class="icon-btn" @click="closeModal"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <div class="modal-body modal-body-scroll">
          <template v-if="formKind === 'mcp'">
            <div v-if="canUseJsonImport" class="mode-switch">
              <button :class="{ active: mcpCreateMode === 'manual' }" @click="mcpCreateMode = 'manual'">{{ t("plugins.manual_create") }}</button>
              <button :class="{ active: mcpCreateMode === 'json' }" @click="mcpCreateMode = 'json'">{{ t("plugins.json_import") }}</button>
            </div>

            <template v-if="mcpCreateMode === 'manual'">
              <div class="compact-form mcp-manual-grid">
                <div class="field-block">
                  <label>{{ t("plugins.form_name") }}</label>
                  <input v-model="formName" :placeholder="t('plugins.ph_mcp_name')" />
                </div>

                <div class="field-block">
                  <label>{{ t("plugins.form_description") }}</label>
                  <input v-model="formDescription" :placeholder="t('plugins.ph_mcp_desc')" />
                </div>

                <div class="field-block">
                  <label>{{ t("plugins.form_transport") }}</label>
                  <select v-model="formTransport" class="transport-select transport-select-fluid">
                    <option value="stdio">stdio</option>
                    <option value="http">Streamable HTTP</option>
                    <option value="websocket">WebSocket</option>
                  </select>
                </div>

                <div class="field-block" v-if="formTransport === 'stdio'">
                  <label>{{ t("plugins.form_command") }}</label>
                  <input v-model="formCommand" placeholder="npx -y @modelcontextprotocol/server-filesystem ." />
                </div>

                <div class="field-block" v-else>
                  <label>Endpoint URL</label>
                  <input v-model="formEndpointUrl" placeholder="https://mcp.example.com/mcp" />
                </div>

                <div class="field-block mcp-field-span">
                  <label>{{ t("plugins.form_headers") }}</label>
                  <textarea
                    v-model="formHeadersLines"
                    rows="4"
                    spellcheck="false"
                    class="headers-textarea"
                    placeholder="Authorization: Bearer xxx&#10;Accept: application/json, text/event-stream"
                  ></textarea>
                  <p class="field-hint">{{ t("plugins.hint_header_format") }}</p>
                </div>

                <details class="advanced-panel mcp-field-span">
                  <summary>{{ t("plugins.advanced_config") }}</summary>
                  <div class="advanced-grid">
                    <div class="field-block">
                      <label>{{ t("plugins.form_project") }}</label>
                      <input v-model="formProjectName" placeholder="e.g. mall-order-service" />
                    </div>

                    <div class="field-block">
                      <label>{{ t("plugins.form_document_url") }}</label>
                      <input v-model="formDocumentUrl" :placeholder="t('plugins.ph_document_url')" />
                    </div>

                    <div class="field-block">
                      <label>{{ t("plugins.form_env") }}</label>
                      <textarea v-model="formEnvJson" rows="5" spellcheck="false"></textarea>
                    </div>

                    <div class="field-block">
                      <label>{{ t("plugins.form_capabilities") }}</label>
                      <input v-model="formCapabilities" placeholder="workspace-browse, api-import" />
                    </div>

                    <label class="check-row">
                      <input v-model="formEnabled" type="checkbox">
                      <span>{{ t("plugins.enable_after_create") }}</span>
                    </label>
                  </div>
                </details>
              </div>
            </template>

            <template v-else>
              <div class="json-import-panel mcp-json-import">
                <label>{{ t("plugins.json_import") }}</label>
                <textarea
                  v-model="mcpJsonText"
                  rows="6"
                  spellcheck="false"
                  class="mcp-json-textarea"
                  :placeholder="mcpJsonPlaceholder"
                ></textarea>
                <p class="json-hint">
                  {{ t("plugins.json_import_hint") }}
                </p>
              </div>
            </template>
          </template>

          <template v-else>
            <div class="settings-group">
              <h4 class="group-title">{{ t("plugins.basic_settings") }}</h4>
              <div class="settings-list">
                <div class="setting-item">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_name") }} <span class="required">*</span></label>
                    <p>{{ t("plugins.hint_name") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formName" placeholder="e.g. Orders API" />
                  </div>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_project") }}</label>
                    <p>{{ t("plugins.hint_project") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formProjectName" placeholder="e.g. mall-order-service" />
                  </div>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_description") }}</label>
                    <p>{{ t("plugins.hint_description") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formDescription" :placeholder="t('plugins.ph_description')" />
                  </div>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <label>Base URL</label>
                    <p>{{ t("plugins.hint_base_url") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formBaseUrl" placeholder="https://api.example.com" />
                  </div>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_document_url") }}</label>
                    <p>{{ t("plugins.hint_doc_url") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formDocumentUrl" placeholder="https://api.example.com/openapi.json" />
                  </div>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_auth_type") }}</label>
                    <p>{{ t("plugins.hint_auth_type") }}</p>
                  </div>
                  <div class="setting-control">
                    <select v-model="formAuthType">
                      <option value="none">none</option>
                      <option value="bearer">bearer</option>
                      <option value="api_key">api_key</option>
                      <option value="basic">basic</option>
                    </select>
                  </div>
                </div>

                <div class="setting-item" v-if="formAuthType === 'bearer' || formAuthType === 'api_key'">
                  <div class="setting-info">
                    <label>{{ formAuthType === "api_key" ? "API Key" : "Bearer Token" }}</label>
                    <p>{{ t("plugins.hint_token_safe") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formAuthToken" type="password" :placeholder="t('plugins.ph_token')" />
                  </div>
                </div>

                <div class="setting-item" v-if="formAuthType === 'api_key'">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_header_name") }}</label>
                    <p>{{ t("plugins.hint_header_name") }}</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formApiKeyHeader" placeholder="X-API-Key" />
                  </div>
                </div>

                <div class="setting-item" v-if="formAuthType === 'basic'">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_username") }}</label>
                  </div>
                  <div class="setting-control">
                    <input v-model="formUsername" placeholder="username" />
                  </div>
                </div>

                <div class="setting-item" v-if="formAuthType === 'basic'">
                  <div class="setting-info">
                    <label>{{ t("plugins.form_password") }}</label>
                  </div>
                  <div class="setting-control">
                    <input v-model="formPassword" type="password" placeholder="password" />
                  </div>
                </div>
              </div>

              <details class="advanced-panel">
                <summary>{{ t("plugins.advanced_config") }}</summary>
                <div class="advanced-grid">
                  <div class="field-block">
                    <label>{{ t("plugins.form_headers_json") }}</label>
                    <textarea v-model="formHeadersJson" rows="5" spellcheck="false"></textarea>
                  </div>

                  <label class="check-row">
                    <input v-model="formEnabled" type="checkbox">
                    <span>{{ t("plugins.enable_after_create") }}</span>
                  </label>
                </div>
              </details>
            </div>
          </template>
        </div>

        <footer class="tools-modal-foot">
          <button class="ghost-btn" @click="closeModal">{{ t("common.cancel") }}</button>
          <button
            v-if="formKind === 'mcp' && canUseJsonImport && mcpCreateMode === 'json'"
            class="primary-btn"
            :disabled="saving"
            @click="importMcpFromJson"
          >
            {{ saving ? t("plugins.importing") : t("plugins.import_mcp_config") }}
          </button>
          <button
            v-else
            class="primary-btn"
            :disabled="saving"
            @click="saveIntegration"
          >
            {{ saving ? t("plugins.saving") : (editingId ? t("plugins.save_changes") : t("plugins.add_server")) }}
          </button>
        </footer>
      </section>
    </div>

    <div
      v-if="managedToolsModalOpen && managedToolsModalKey"
      class="tools-modal-backdrop"
      @click.self="closeManagedToolsModal"
    >
      <section class="tools-modal managed-tools-dialog">
        <header class="tools-modal-head">
          <div>
            <h3>{{ managedToolsModalTitle }}</h3>
            <p>{{ t("plugins.managed_tools_desc") }}</p>
          </div>
          <button type="button" class="icon-btn" @click="closeManagedToolsModal">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </header>
        <div class="modal-body modal-body-scroll">
          <template v-if="toolsLoadingKey === managedToolsModalKey">
            <p class="tools-empty">{{ t("plugins.loading_tools") }}</p>
          </template>
          <template v-else-if="!managedToolsModalTools.length">
            <p class="tools-empty">{{ t("plugins.no_tools_exposed") }}</p>
          </template>
          <div v-else class="tool-list">
            <div v-for="tool in managedToolsModalTools" :key="tool.key" class="tool-item">
              <div class="tool-item-head">
                <strong>{{ tool.name }}</strong>
                <span class="tool-kind">{{ tool.source_kind }}</span>
              </div>
              <p>{{ tool.description || t("plugins.no_description") }}</p>
            </div>
          </div>
        </div>
        <footer class="tools-modal-foot">
          <button type="button" class="ghost-btn" @click="closeManagedToolsModal">{{ t("common.close") }}</button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tools-tab-pane {
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: var(--text);
}

.pane-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.head-desc {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}

.main-tabs {
  display: flex;
  gap: 14px;
  border-bottom: 1px solid var(--border);
}

.main-tabs button {
  position: relative;
  padding: 10px 2px 14px;
  background: transparent;
  border: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
}

.main-tabs button.active {
  color: var(--text);
}

.main-tabs button.active::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 3px;
  border-radius: 999px;
  background: var(--accent);
}

.count {
  margin-left: 6px;
  color: var(--muted);
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.integration-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 18px;
  justify-items: start;
}

.integration-card {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: var(--shadow-soft);
  width: 100%;
  max-width: 520px;
  box-sizing: border-box;
  color: var(--text);
}

.integration-card--managed {
  border-color: var(--border);
  border-color: color-mix(in srgb, var(--blue) 35%, var(--border));
  max-width: 440px;
  gap: 12px;
}

.integration-card--managed .card-desc {
  min-height: 0;
}

.managed-card-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.managed-action-bar {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.managed-action-btn {
  flex: 1;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 11px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.managed-action-btn--tools {
  background: var(--surface-soft);
  border-color: var(--border);
  color: var(--text);
}

.managed-action-btn--tools:hover:not(:disabled) {
  background: var(--surface-muted);
  border-color: var(--border-strong);
}

.managed-action-btn--test {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--bg);
}

.managed-action-btn--test:hover:not(:disabled) {
  filter: brightness(1.08);
}

.managed-action-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--muted) 35%, transparent);
}

.managed-action-btn--test:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 40%, transparent);
}

.managed-action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.managed-action-btn i {
  font-size: 14px;
  flex-shrink: 0;
  opacity: 0.92;
}

.integration-card-head,
.card-title-row,
.integration-actions,
.tag-row,
.provider-strip,
.mode-switch,
.transport-grid {
  display: flex;
  align-items: center;
  gap: 10px;
}

.integration-card-head {
  justify-content: space-between;
}

.card-title-row h5,
.card-title-row strong {
  margin: 0;
  font-size: 16px;
  color: var(--text);
}

.card-desc {
  margin: 0;
  color: var(--muted);
  line-height: 1.5;
  min-height: 42px;
}

.integration-meta {
  display: grid;
  gap: 10px;
}

.meta-item {
  display: flex;
  gap: 10px;
  align-items: center;
  color: var(--muted);
  font-size: 13px;
  word-break: break-all;
}

.meta-badge,
.provider-chip,
.tag-row span,
.tool-kind {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  padding: 4px 10px;
  font-size: 12px;
  color: var(--muted);
}

.tag-row {
  flex-wrap: wrap;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--border-strong);
}

.status-dot.active {
  background: var(--green);
}

.ghost-btn,
.primary-btn,
.icon-btn,
.mode-switch button,
.transport-card {
  border-radius: 12px;
  border: 1px solid var(--border-strong);
  padding: 10px 14px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 14px;
}

.ghost-btn:hover,
.primary-btn:hover,
.icon-btn:hover,
.mode-switch button:hover,
.transport-card:hover {
  border-color: var(--muted);
}

.ghost-btn.danger {
  color: var(--red);
}

.primary-btn {
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
}

.primary-btn:disabled,
.ghost-btn:disabled,
.mode-switch button:disabled,
.transport-card:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.plugins-empty {
  padding: 48px 18px;
  border: 1px dashed var(--border-strong);
  border-radius: 18px;
  color: var(--muted);
  text-align: center;
}

.plugins-empty--error {
  border-color: color-mix(in srgb, var(--red) 55%, var(--border));
  color: var(--red);
}

.provider-strip {
  flex-wrap: wrap;
}

.tools-empty {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.tool-list {
  display: grid;
  gap: 12px;
}

.tool-item {
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}

.tool-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tool-item p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.tool-item-head strong {
  color: var(--text);
}

.tools-modal-backdrop {
  position: fixed;
  inset: 0;
  background: color-mix(in srgb, var(--bg) 40%, rgb(15 23 42 / 0.45));
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 24px;
}

.tools-modal {
  display: flex;
  flex-direction: column;
  width: min(860px, 100%);
  max-height: calc(100vh - 48px);
  overflow: hidden;
  border-radius: 24px;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-panel);
}

.managed-tools-dialog {
  width: min(560px, 100%);
}

.tools-modal-head,
.tools-modal-foot {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
}

.tools-modal-head h3 {
  margin: 0 0 8px;
  font-size: 22px;
  color: var(--text);
}

.tools-modal-head p {
  margin: 0;
  color: var(--muted);
}

.tools-modal-foot {
  border-top: 1px solid var(--border);
  border-bottom: 0;
  justify-content: flex-end;
}

.icon-btn {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.modal-body {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 20px;
  padding: 24px;
}

.modal-body-scroll {
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-gutter: stable;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--border-strong) transparent;
}

.modal-body-scroll::-webkit-scrollbar {
  width: 8px;
}

.modal-body-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.modal-body-scroll::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 999px;
}

.modal-body-scroll::-webkit-scrollbar-thumb:hover {
  background: var(--muted);
}

.settings-group,
.compact-form,
.json-import-panel,
.field-block,
.advanced-grid {
  display: grid;
  gap: 12px;
}

.mode-switch {
  display: flex;
  padding: 5px;
  border-radius: 14px;
  background: var(--surface-muted);
  width: 100%;
  max-width: 420px;
  gap: 4px;
}

.mode-switch button {
  flex: 1;
  min-width: 0;
  border-color: transparent;
  background: transparent;
  color: var(--muted);
  border-radius: 11px;
  padding: 10px 14px;
  font-weight: 600;
}

.mode-switch button.active {
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-soft);
}

.field-block label,
.group-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.transport-select {
  width: min(260px, 100%);
}

.transport-select-fluid {
  width: 100%;
  max-width: none;
}

.mcp-manual-grid {
  align-items: start;
}

@media (min-width: 640px) {
  .mcp-manual-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 20px;
    row-gap: 14px;
  }

  .mcp-field-span {
    grid-column: 1 / -1;
  }
}

.mcp-json-import {
  gap: 10px;
}

.mcp-json-textarea {
  resize: vertical;
  min-height: 90px;
}

.headers-textarea {
  resize: vertical;
  min-height: 88px;
}

.advanced-panel {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface-soft);
  padding: 14px 16px;
}

.advanced-panel summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--text);
}

.advanced-grid {
  margin-top: 14px;
}

.json-import-panel textarea,
.advanced-grid textarea,
.field-block textarea,
.field-block input,
.field-block select,
.settings-list input,
.settings-list select {
  width: 100%;
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 14px;
  color: var(--text);
  background: var(--surface-soft);
}

.tools-modal .field-block select,
.tools-modal .settings-list select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  min-height: 44px;
  padding-right: 42px;
  cursor: pointer;
  line-height: 1.35;
  background-color: var(--surface-soft);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' fill='none' viewBox='0 0 24 24'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  background-size: 18px;
}

.tools-modal .field-block select:hover,
.tools-modal .settings-list select:hover {
  border-color: var(--muted);
}

.tools-modal .field-block select:focus,
.tools-modal .settings-list select:focus {
  outline: none;
  border-color: var(--border-strong);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--muted) 28%, transparent);
}

.json-import-panel textarea:not(.mcp-json-textarea),
.advanced-grid textarea,
.field-block textarea:not(.headers-textarea):not(.mcp-json-textarea) {
  resize: vertical;
  min-height: 120px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.json-import-panel textarea,
.advanced-grid textarea,
.field-block textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.json-hint {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
}

.json-hint code {
  padding: 2px 6px;
  border-radius: 8px;
  background: var(--surface-muted);
  color: var(--text);
}

.settings-list {
  display: grid;
  gap: 12px;
}

.setting-item {
  display: grid;
  grid-template-columns: minmax(180px, 240px) 1fr;
  gap: 16px;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 16px;
  background: var(--surface-soft);
}

.setting-info {
  display: grid;
  gap: 6px;
}

.setting-info label {
  font-weight: 700;
  color: var(--text);
}

.setting-info p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}

.setting-control {
  display: grid;
  gap: 10px;
}

.required {
  color: var(--red);
}

.field-hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.check-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-size: 14px;
}

@media (max-width: 900px) {
  .setting-item {
    grid-template-columns: 1fr;
  }

  .pane-header,
  .transport-grid {
    flex-direction: column;
    align-items: stretch;
  }

  .mode-switch {
    width: 100%;
  }

  .mode-switch button {
    min-width: 0;
    flex: 1;
  }
}
</style>

<style>
:root[data-theme="dark"] .tools-modal-backdrop {
  background: rgb(0 0 0 / 0.72);
}

:root[data-theme="dark"] .tools-modal .field-block select,
:root[data-theme="dark"] .tools-modal .settings-list select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' fill='none' viewBox='0 0 24 24'%3E%3Cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
}
</style>
