<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { NSelect, type SelectOption } from "naive-ui";

import { api } from "../../../services/api";
import type {
  ModelCapabilities,
  ModelCapabilitiesOverride,
  ModelConfigPublic,
  ModelConfigUpdateRequest,
  OAuthModelItem,
  OAuthProviderProfile,
  OAuthStatusResponse,
} from "../../../types";

type MessageTone = "success" | "error";
type CapabilityKey = keyof ModelCapabilities;

interface CapabilityOption {
  key: CapabilityKey;
  label: string;
  hint: string;
}

const TRANSPORT_OPTIONS: SelectOption[] = [
  { label: "OpenAI Chat Completions", value: "openai_chat_completions" },
  { label: "Anthropic Messages", value: "anthropic_messages" },
  { label: "Google Gemini Generate Content", value: "google_gemini_generate_content" },
];

const loading = ref(false);
const saving = ref(false);
const showEditorModal = ref(false);
const editingModelName = ref<string | null>(null);
const busyActionKey = ref("");
const modelConfigs = ref<ModelConfigPublic[]>([]);
const messageVisible = ref(false);
const messageText = ref("");
const messageTone = ref<MessageTone>("success");
let messageTimer: ReturnType<typeof setTimeout> | null = null;
const showCapabilities = ref(false);

// OAuth provider presets
const oauthProviders = ref<OAuthProviderProfile[]>([]);
const oauthFlowState = ref<string | null>(null);
const oauthFlowStatus = ref<OAuthStatusResponse | null>(null);
const oauthPolling = ref(false);
let oauthPollTimer: ReturnType<typeof setInterval> | null = null;

// OAuth model discovery
const oauthAvailableModels = ref<OAuthModelItem[]>([]);
const oauthModelsFetching = ref(false);
const oauthSelectedModelId = ref<string | null>(null);
// Azure AD and providers that need a custom resource base URL
const oauthCustomBaseUrl = ref("");

const capabilityOptions: CapabilityOption[] = [
  { key: "tool_calling", label: "工具调用", hint: "允许模型发起工具调用" },
  { key: "vision", label: "视觉识别", hint: "支持图片理解与视觉输入" },
  { key: "reasoning", label: "推理模式", hint: "支持更长链路的推理输出" },
  { key: "multi_image", label: "多图输入", hint: "同一轮可输入多张图片" },
  { key: "file_input", label: "文件输入", hint: "支持文件或附件类输入" },
  { key: "pdf_input", label: "PDF 输入", hint: "支持 PDF 文档输入" },
  { key: "json_mode", label: "JSON 模式", hint: "支持结构化 JSON 输出" },
  { key: "streaming", label: "流式响应", hint: "支持流式输出消息" },
  { key: "parallel_tool_calls", label: "并行工具", hint: "支持并行工具调用" },
  { key: "image_url_input", label: "图片 URL", hint: "支持图片链接输入" },
  { key: "image_base64_input", label: "Base64 图片", hint: "支持 Base64 图片输入" },
];

const baseCapabilities: ModelCapabilities = {
  text_input: true,
  text_output: true,
  tool_calling: true,
  vision: false,
  multi_image: false,
  file_input: false,
  pdf_input: false,
  reasoning: true,
  json_mode: false,
  streaming: true,
  parallel_tool_calls: false,
  image_url_input: true,
  image_base64_input: true,
};

const modelDraft = reactive<ModelConfigUpdateRequest>({
  model_name: "",
  provider: "",
  transport: "openai_chat_completions",
  base_url: "",
  api_key: null,
  is_active: false,
  use_provider_defaults: true,
  capability_overrides: {},
  auth_type: "api_key",
  oauth_provider: null,
  oauth_refresh_token: null,
});

const capabilityDraft = reactive<ModelCapabilities>({ ...baseCapabilities });

const isEditing = computed(() => Boolean(editingModelName.value));
const isOAuth = computed(() => modelDraft.auth_type === "oauth2");

const selectedOAuthProfile = computed<OAuthProviderProfile | null>(() => {
  if (!modelDraft.oauth_provider) return null;
  return oauthProviders.value.find((p) => p.key === modelDraft.oauth_provider) ?? null;
});

const providerOptions = computed<SelectOption[]>(() => {
  const seen = new Set<string>();
  return modelConfigs.value
    .map((item) => item.provider.trim())
    .filter((provider) => {
      if (!provider) return false;
      const normalized = provider.toLowerCase();
      if (seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    })
    .sort((left, right) => left.localeCompare(right))
    .map((provider) => ({ label: provider, value: provider }));
});

const oauthProviderOptions = computed<SelectOption[]>(() =>
  oauthProviders.value.map((p) => ({ label: p.display_name, value: p.key })),
);

const oauthModelOptions = computed<SelectOption[]>(() =>
  oauthAvailableModels.value.map((m) => ({ label: `${m.id}  (${m.name})`, value: m.id })),
);

const oauthAuthSuccess = computed(
  () => oauthFlowStatus.value?.status === "completed" || Boolean(modelDraft.oauth_refresh_token),
);

const oauthNeedsBaseUrl = computed(() => selectedOAuthProfile.value?.requires_base_url ?? false);

const oauthHasModelListing = computed(() => selectedOAuthProfile.value?.has_model_listing ?? false);

/** 支持拉取模型列表时，有列表后配置名由所选模型决定，不再单独展示输入框 */
const showOAuthConfigNameField = computed(
  () => !oauthHasModelListing.value || oauthAvailableModels.value.length === 0,
);

onMounted(() => {
  void loadSettings();
  void loadOAuthProviders();
});

onBeforeUnmount(() => {
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
  stopOAuthPoll();
});

watch(
  () => [showEditorModal.value, modelDraft.provider, modelDraft.transport, modelDraft.use_provider_defaults] as const,
  ([visible, provider, transport, useProviderDefaults]) => {
    if (!visible || !useProviderDefaults) return;
    applyCapabilityDraft(inferCapabilities(provider, transport || "openai_chat_completions"));
  },
);

async function loadSettings() {
  loading.value = true;
  try {
    modelConfigs.value = await api.listModelConfigs();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "加载模型设置失败。");
  } finally {
    loading.value = false;
  }
}

async function loadOAuthProviders() {
  try {
    const res = await api.listOAuthProviders();
    oauthProviders.value = res.providers;
  } catch {
    // non-critical, silently ignore
  }
}

function showMessage(tone: MessageTone, text: string) {
  messageTone.value = tone;
  messageText.value = text;
  messageVisible.value = true;

  if (messageTimer) clearTimeout(messageTimer);

  messageTimer = setTimeout(() => {
    messageVisible.value = false;
    messageTimer = null;
  }, 2600);
}

function resetModelDraft() {
  modelDraft.model_name = "";
  modelDraft.provider = "";
  modelDraft.transport = "openai_chat_completions";
  modelDraft.base_url = "";
  modelDraft.api_key = null;
  modelDraft.is_active = modelConfigs.value.length === 0;
  modelDraft.use_provider_defaults = true;
  modelDraft.capability_overrides = {};
  modelDraft.auth_type = "api_key";
  modelDraft.oauth_provider = null;
  modelDraft.oauth_refresh_token = null;
  resetOAuthFlow();
  applyCapabilityDraft(inferCapabilities("", modelDraft.transport));
}

function openCreateModal() {
  editingModelName.value = null;
  resetModelDraft();
  showCapabilities.value = false;
  showEditorModal.value = true;
}

function openEditModal(item: ModelConfigPublic) {
  editingModelName.value = item.name;
  modelDraft.model_name = item.name;
  modelDraft.provider = item.provider;
  modelDraft.transport = item.transport;
  modelDraft.base_url = item.api_base_url;
  modelDraft.api_key = null;
  modelDraft.is_active = item.is_active;
  modelDraft.use_provider_defaults = !hasCapabilityOverrides(item.capability_overrides);
  modelDraft.capability_overrides = { ...item.capability_overrides };
  modelDraft.auth_type = item.auth_type ?? "api_key";
  modelDraft.oauth_provider = item.oauth_provider ?? null;
  modelDraft.oauth_refresh_token = null;
  oauthCustomBaseUrl.value = item.api_base_url;
  resetOAuthFlow();
  if (item.auth_type === "oauth2" && item.oauth_provider && item.name) {
    const profile = oauthProviders.value.find((p) => p.key === item.oauth_provider);
    if (profile?.has_model_listing) {
      oauthAvailableModels.value = [
        { id: item.name, raw_id: item.name, name: item.description?.trim() || item.name },
      ];
      oauthSelectedModelId.value = item.name;
    }
  }
  applyCapabilityDraft(item.capabilities);
  showCapabilities.value = false;
  showEditorModal.value = true;
}

function closeEditorModal() {
  showEditorModal.value = false;
  editingModelName.value = null;
}

function applyCapabilityDraft(capabilities: Partial<ModelCapabilities>) {
  capabilityOptions.forEach((option) => {
    capabilityDraft[option.key] = Boolean(capabilities[option.key] ?? baseCapabilities[option.key]);
  });
}

function inferCapabilities(provider: string, transport: string): ModelCapabilities {
  const normalizedProvider = provider.trim().toLowerCase();
  const normalizedTransport = transport.trim().toLowerCase();
  const capabilities: ModelCapabilities = { ...baseCapabilities };

  const openAiVisionProviders = new Set([
    "openai", "anthropic", "deepseek", "qwen", "dashscope", "zhipu", "glm",
    "openrouter", "xai", "minimax", "volcengine", "doubao", "hunyuan",
    "baidu", "ernie", "moonshot", "kimi",
  ]);

  if (normalizedTransport === "anthropic_messages") {
    capabilities.vision = true;
    capabilities.image_url_input = false;
    capabilities.image_base64_input = true;
    return capabilities;
  }

  if (normalizedTransport === "google_gemini_generate_content") {
    capabilities.vision = true;
    capabilities.multi_image = true;
    capabilities.file_input = true;
    capabilities.image_url_input = false;
    capabilities.image_base64_input = true;
    return capabilities;
  }

  capabilities.image_url_input = true;
  capabilities.image_base64_input = true;
  if (openAiVisionProviders.has(normalizedProvider)) {
    capabilities.vision = true;
  }
  return capabilities;
}

function buildCapabilityOverrides(): ModelCapabilitiesOverride {
  const overrides: ModelCapabilitiesOverride = {};
  capabilityOptions.forEach((option) => {
    overrides[option.key] = capabilityDraft[option.key];
  });
  return overrides;
}

function hasCapabilityOverrides(overrides: ModelCapabilitiesOverride | undefined | null) {
  if (!overrides) return false;
  return Object.values(overrides).some((value) => value !== null && value !== undefined);
}

async function saveModel() {
  if (isOAuth.value && oauthHasModelListing.value && oauthAvailableModels.value.length > 0) {
    if (!oauthSelectedModelId.value?.trim()) {
      showMessage("error", "请先获取可用模型并在列表中选择要使用的模型。");
      return;
    }
    modelDraft.model_name = oauthSelectedModelId.value.trim();
  }

  if (!modelDraft.model_name.trim()) {
    showMessage("error", "配置名称不能为空。");
    return;
  }

  if (isOAuth.value) {
    if (!modelDraft.oauth_provider) {
      showMessage("error", "OAuth 2.0 模式需要选择提供商。");
      return;
    }
    if (oauthNeedsBaseUrl.value && !oauthCustomBaseUrl.value.trim()) {
      showMessage("error", "该提供商需要填写资源端点 (Base URL)。");
      return;
    }
  } else {
    if (!modelDraft.provider.trim() || !modelDraft.transport?.trim() || !modelDraft.base_url.trim()) {
      showMessage("error", "供应商、协议和 Base URL 不能为空。");
      return;
    }
  }

  saving.value = true;

  // For OAuth mode, auto-fill provider/transport/base_url from the profile
  let provider = modelDraft.provider.trim().toLowerCase();
  let transport = modelDraft.transport ?? "openai_chat_completions";
  let base_url = modelDraft.base_url.trim();

  if (isOAuth.value && selectedOAuthProfile.value) {
    const profile = selectedOAuthProfile.value;
    provider = profile.key;
    transport = profile.default_transport || "openai_chat_completions";
    base_url = oauthNeedsBaseUrl.value
      ? oauthCustomBaseUrl.value.trim()
      : (profile.api_base_url || "");
  }

  const payload: ModelConfigUpdateRequest = {
    model_name: modelDraft.model_name.trim(),
    provider,
    transport,
    base_url,
    api_key: isOAuth.value ? null : (modelDraft.api_key?.trim() || null),
    is_active: modelDraft.is_active,
    use_provider_defaults: modelDraft.use_provider_defaults ?? true,
    capability_overrides: modelDraft.use_provider_defaults ? {} : buildCapabilityOverrides(),
    auth_type: modelDraft.auth_type,
    oauth_provider: isOAuth.value ? (modelDraft.oauth_provider || null) : null,
    oauth_refresh_token: isOAuth.value ? (modelDraft.oauth_refresh_token?.trim() || null) : null,
  };

  try {
    const saved = editingModelName.value
      ? await api.editModelConfig(editingModelName.value, payload)
      : await api.updateModelConfig(payload);

    showMessage("success", editingModelName.value ? `模型已更新：${saved.name}` : `模型已创建：${saved.name}`);
    closeEditorModal();
    await loadSettings();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "保存模型配置失败。");
  } finally {
    saving.value = false;
  }
}

function actionKey(modelName: string, action: string) {
  return `${modelName}:${action}`;
}

async function withAction(modelName: string, action: string, runner: () => Promise<void>) {
  busyActionKey.value = actionKey(modelName, action);
  try {
    await runner();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "模型操作失败。");
  } finally {
    busyActionKey.value = "";
  }
}

async function testConnection(item: ModelConfigPublic) {
  await withAction(item.name, "test", async () => {
    const result = await api.testModelConfigConnection(item.name);
    if (result.ok) {
      if (result.preview) {
        showMessage("success", `连接测试成功：${item.name}，响应：${result.preview}`);
      } else if (result.latency_ms) {
        showMessage("success", `连接测试成功：${item.name}，延迟 ${result.latency_ms}ms`);
      } else {
        showMessage("success", `连接测试成功：${item.name}`);
      }
      return;
    }
    showMessage("error", `连接测试失败：${item.name}`);
  });
}

async function activateModel(item: ModelConfigPublic) {
  await withAction(item.name, "activate", async () => {
    await api.activateModelConfig(item.name);
    showMessage("success", `已激活模型：${item.name}`);
    await loadSettings();
  });
}

// ── OAuth provider selection ──────────────────────────────────────────────────

function onOAuthProviderChange(key: string | null) {
  if (!key) {
    oauthAvailableModels.value = [];
    oauthSelectedModelId.value = null;
    return;
  }
  // Clear model list when provider changes
  oauthAvailableModels.value = [];
  oauthSelectedModelId.value = null;
  // Reset auth state for new provider
  resetOAuthFlow();
}

// ── OAuth Authorization Code flow ─────────────────────────────────────────────

function resetOAuthFlow() {
  stopOAuthPoll();
  oauthFlowState.value = null;
  oauthFlowStatus.value = null;
  oauthPolling.value = false;
  oauthAvailableModels.value = [];
  oauthSelectedModelId.value = null;
}

function stopOAuthPoll() {
  if (oauthPollTimer !== null) {
    clearInterval(oauthPollTimer);
    oauthPollTimer = null;
  }
}

function buildOAuthRedirectUri(provider: string) {
  const origin = `${window.location.protocol}//${window.location.hostname}:8000`;
  const normalized = provider.trim().toLowerCase();
  if (normalized === "github") return `${origin}/api/v1/oauth/github/callback`;
  if (normalized === "google") return `${origin}/api/v1/oauth/google/callback`;
  if (normalized === "azure_ad") return `${origin}/api/v1/oauth/azure/callback`;
  return `${origin}/api/v1/oauth/callback`;
}

async function launchOAuth() {
  if (!modelDraft.oauth_provider) {
    showMessage("error", "请先选择 OAuth 提供商。");
    return;
  }
  const provider = modelDraft.oauth_provider;
  const redirectUri = buildOAuthRedirectUri(provider);

  try {
    const res = await api.startOAuthFlow({ provider, redirect_uri: redirectUri });

    oauthFlowState.value = res.state;
    oauthFlowStatus.value = { state: res.state, status: "pending" };
    oauthPolling.value = true;

    window.open(res.authorization_url, "_blank", "noopener,noreferrer");

    stopOAuthPoll();
    oauthPollTimer = setInterval(async () => {
      try {
        const status = await api.getOAuthStatus(res.state);
        oauthFlowStatus.value = status;
        if (status.status === "completed") {
          stopOAuthPoll();
          oauthPolling.value = false;
          if (status.refresh_token) {
            modelDraft.oauth_refresh_token = status.refresh_token;
          }
          showMessage("success", "OAuth 授权成功！可点击「获取可用模型」选择要使用的模型。");
        } else if (status.status === "failed") {
          stopOAuthPoll();
          oauthPolling.value = false;
          showMessage("error", `OAuth 授权失败：${status.error || "未知错误"}`);
        }
      } catch {
        // network hiccup — keep polling
      }
    }, 2000);
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "启动 OAuth 流程失败。");
  }
}

// ── OAuth model discovery ─────────────────────────────────────────────────────

async function fetchOAuthModels() {
  if (!modelDraft.oauth_provider) {
    showMessage("error", "请先选择 OAuth 提供商。");
    return;
  }
  oauthModelsFetching.value = true;
  try {
    const res = await api.listOAuthModels(
      modelDraft.oauth_provider,
      oauthFlowState.value ?? null,
      oauthNeedsBaseUrl.value ? oauthCustomBaseUrl.value.trim() || null : null,
    );
    oauthAvailableModels.value = res.models;
    if (res.models.length === 0) {
      showMessage("error", "未找到可用模型，请确认 .env 中凭据已配置或先完成 OAuth 授权。");
    }
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "获取模型列表失败。");
  } finally {
    oauthModelsFetching.value = false;
  }
}

function onOAuthModelSelect(modelId: string | null) {
  oauthSelectedModelId.value = modelId;
  if (modelId) {
    modelDraft.model_name = modelId;
  }
}

async function deleteModel(item: ModelConfigPublic) {
  const confirmed = window.confirm(`确定删除模型"${item.name}"吗？`);
  if (!confirmed) return;

  await withAction(item.name, "delete", async () => {
    await api.deleteModelConfig(item.name);
    showMessage("success", `已删除模型：${item.name}`);
    await loadSettings();
  });
}
</script>

<template>
  <section class="settings-pane">
    <transition name="settings-toast">
      <div
        v-if="messageVisible"
        class="settings-message"
        :class="messageTone === 'success' ? 'is-success' : 'is-error'"
      >
        {{ messageText }}
      </div>
    </transition>

    <div class="settings-pane-head">
      <div>
        <h3>模型设置</h3>
        <p>维护当前系统可用的大模型配置，并显式区分供应商、协议与接入地址。</p>
      </div>
    </div>

    <div class="settings-pane-block settings-model-grid-shell">
      <div class="settings-model-grid">
        <article
          v-for="item in modelConfigs"
          :key="item.id ?? item.name"
          class="settings-model-card settings-model-card-static"
        >
          <div class="settings-model-card__header">
            <span v-if="item.is_active" class="settings-model-card__badge settings-model-card__badge-current">
              当前使用
            </span>
          </div>

          <div class="settings-model-card__name">
            <strong>{{ item.name }}</strong>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-server"></i>
            <span>{{ item.provider }}</span>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-arrows-rotate"></i>
            <span>{{ item.transport }}</span>
          </div>

          <div class="settings-model-card__stats settings-model-card__stats-plain">
            <div class="settings-model-card__stat">
              <span v-if="item.auth_type === 'oauth2'">
                <i class="fa-solid fa-shield-halved"></i>
                OAuth{{ item.oauth_provider ? ` · ${item.oauth_provider}` : " 2.0" }}
              </span>
              <span v-else>API Key</span>
              <strong v-if="item.auth_type === 'oauth2'">
                {{ item.has_oauth_refresh_token ? "令牌已获取 ✓" : "未配置" }}
              </strong>
              <strong v-else>{{ item.has_secret ? "已配置" : "未配置" }}</strong>
            </div>
            <div class="settings-model-card__stat settings-model-card__stat-full">
              <span>接口地址</span>
              <strong>{{ item.api_base_url }}</strong>
            </div>
          </div>

          <div class="settings-model-card__spacer"></div>

          <div class="settings-model-card__actions">
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-test"
              :disabled="busyActionKey === actionKey(item.name, 'test')"
              title="测试连接"
              @click="testConnection(item)"
            >
              <i
                class="fa-solid"
                :class="busyActionKey === actionKey(item.name, 'test') ? 'fa-spinner fa-spin' : 'fa-plug-circle-check'"
              ></i>
            </button>
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-activate"
              :disabled="item.is_active || busyActionKey === actionKey(item.name, 'activate')"
              title="激活模型"
              @click="activateModel(item)"
            >
              <i
                class="fa-solid"
                :class="busyActionKey === actionKey(item.name, 'activate') ? 'fa-spinner fa-spin' : 'fa-circle-check'"
              ></i>
            </button>
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-edit"
              title="编辑模型"
              @click="openEditModal(item)"
            >
              <i class="fa-solid fa-pen-to-square"></i>
            </button>
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-danger"
              :disabled="busyActionKey === actionKey(item.name, 'delete')"
              title="删除模型"
              @click="deleteModel(item)"
            >
              <i
                class="fa-solid"
                :class="busyActionKey === actionKey(item.name, 'delete') ? 'fa-spinner fa-spin' : 'fa-trash-can'"
              ></i>
            </button>
          </div>
        </article>

        <button type="button" class="settings-model-card settings-model-card-add" @click="openCreateModal">
          <div class="settings-model-card-add__icon">+</div>
          <div class="settings-model-card-add__body">
            <strong>新增模型</strong>
            <p>创建新的模型配置</p>
          </div>
        </button>
      </div>
    </div>

    <!-- editor modal -->
    <div v-if="showEditorModal" class="settings-modal-overlay" @click.self="closeEditorModal">
      <section class="settings-modal-card settings-modal-card-clean">
        <div class="settings-modal-head">
          <div>
            <h4>{{ isEditing ? "编辑模型" : "新增模型" }}</h4>
            <p>{{ isEditing ? "修改已有模型配置" : "创建新的模型配置" }}</p>
          </div>
          <button type="button" class="settings-modal-close" @click="closeEditorModal">×</button>
        </div>

        <!-- ── 认证方式切换 ──────────────────────────────────────────── -->
        <div class="form-grid two">
          <div class="full settings-auth-type-row">
            <span class="settings-auth-type-label">认证方式</span>
            <div class="settings-auth-type-btns">
              <button
                type="button"
                class="settings-auth-type-btn"
                :class="{ active: modelDraft.auth_type === 'api_key' }"
                @click="modelDraft.auth_type = 'api_key'"
              >
                <i class="fa-solid fa-key"></i> API Key
              </button>
              <button
                type="button"
                class="settings-auth-type-btn"
                :class="{ active: modelDraft.auth_type === 'oauth2' }"
                @click="modelDraft.auth_type = 'oauth2'"
              >
                <i class="fa-solid fa-shield-halved"></i> OAuth 2.0
              </button>
            </div>
          </div>

          <!-- ── API Key 模式 ──────────────────────────────────────────── -->
          <template v-if="!isOAuth">
            <label>
              <span>模型名称</span>
              <input v-model="modelDraft.model_name" type="text" placeholder="claude-opus-4-7 / gpt-5.4" />
            </label>

            <label class="settings-provider-field">
              <span>供应商</span>
              <NSelect
                v-model:value="modelDraft.provider"
                class="settings-provider-select"
                menu-class="settings-provider-select-menu"
                filterable
                tag
                clearable
                :options="providerOptions"
                placeholder="请选择或输入供应商"
              />
            </label>

            <label class="settings-provider-field">
              <span>协议</span>
              <NSelect
                v-model:value="modelDraft.transport"
                class="settings-provider-select"
                menu-class="settings-provider-select-menu"
                :options="TRANSPORT_OPTIONS"
                placeholder="请选择协议类型"
              />
            </label>

            <label>
              <span>接口地址</span>
              <input v-model="modelDraft.base_url" type="text" placeholder="https://api.deepseek.com/v1" />
            </label>

            <label class="full">
              <span>API Key</span>
              <input v-model="modelDraft.api_key" type="password" placeholder="留空则保留当前密钥" />
              <small>系统不会回显已保存的密钥内容。</small>
            </label>
          </template>

          <!-- ── OAuth 2.0 模式 ──────────────────────────────────────────── -->
          <template v-else>
            <!-- Step 1: Provider -->
            <label class="full settings-provider-field">
              <span>OAuth 提供商</span>
              <NSelect
                v-model:value="modelDraft.oauth_provider"
                class="settings-provider-select"
                menu-class="settings-provider-select-menu"
                :options="oauthProviderOptions"
                placeholder="选择 OAuth 提供商"
                clearable
                @update:value="onOAuthProviderChange"
              />
              <small v-if="selectedOAuthProfile?.notes" class="oauth-provider-note">
                {{ selectedOAuthProfile.notes }}
              </small>
            </label>

            <!-- Azure / custom resource Base URL -->
            <label v-if="oauthNeedsBaseUrl" class="full">
              <span>资源端点（接口地址）</span>
              <input
                v-model="oauthCustomBaseUrl"
                type="text"
                placeholder="https://your-resource.openai.azure.com"
              />
              <small>该提供商的 API 端点因资源而异，请填写您的具体地址。</small>
            </label>

            <!-- Step 2: OAuth Authorization -->
            <div v-if="modelDraft.oauth_provider" class="full oauth-launch-section">
              <div class="oauth-step-label">
                <span class="oauth-step-num">1</span>
                <span>浏览器授权</span>
                <i v-if="oauthAuthSuccess" class="fa-solid fa-check oauth-step-done"></i>
              </div>

              <!-- Success: refresh token obtained -->
              <div v-if="modelDraft.oauth_refresh_token" class="oauth-token-status oauth-token-ok">
                <i class="fa-solid fa-circle-check"></i>
                已获取 Refresh Token，授权完成
                <button type="button" class="oauth-token-clear" @click="modelDraft.oauth_refresh_token = null; resetOAuthFlow()">
                  清除
                </button>
              </div>

              <!-- Polling / pending / failed -->
              <div v-else-if="oauthFlowStatus" class="oauth-token-status" :class="{
                'oauth-token-pending': oauthFlowStatus.status === 'pending',
                'oauth-token-ok': oauthFlowStatus.status === 'completed',
                'oauth-token-error': oauthFlowStatus.status === 'failed',
              }">
                <i class="fa-solid" :class="{
                  'fa-spinner fa-spin': oauthFlowStatus.status === 'pending',
                  'fa-circle-check': oauthFlowStatus.status === 'completed',
                  'fa-circle-xmark': oauthFlowStatus.status === 'failed',
                }"></i>
                <span v-if="oauthFlowStatus.status === 'pending'">等待用户在浏览器中完成授权…</span>
                <span v-else-if="oauthFlowStatus.status === 'completed'">授权成功</span>
                <span v-else>授权失败：{{ oauthFlowStatus.error }}</span>
                <button v-if="oauthFlowStatus.status !== 'pending'" type="button" class="oauth-token-clear" @click="resetOAuthFlow()">
                  重置
                </button>
              </div>

              <button
                type="button"
                class="oauth-launch-btn"
                :disabled="oauthPolling || !modelDraft.oauth_provider"
                @click="launchOAuth"
              >
                <i class="fa-solid" :class="oauthPolling ? 'fa-spinner fa-spin' : 'fa-arrow-up-right-from-square'"></i>
                {{ oauthPolling ? "等待授权中…" : (oauthAuthSuccess ? "重新授权" : "启动 OAuth 授权") }}
              </button>

              <p class="oauth-env-hint">
                <i class="fa-solid fa-circle-info"></i>
                Client ID / Client Secret 等凭据已在后端 <code>.env</code> 中配置，无需在此填写。
              </p>
            </div>

            <!-- Step 3: Model Discovery (shown once provider is selected) -->
            <div v-if="modelDraft.oauth_provider" class="full oauth-models-section">
              <div class="oauth-step-label">
                <span class="oauth-step-num">2</span>
                <span>选择模型</span>
                <i v-if="oauthSelectedModelId" class="fa-solid fa-check oauth-step-done"></i>
              </div>

              <div class="oauth-models-row">
                <button
                  type="button"
                  class="oauth-fetch-btn"
                  :disabled="oauthModelsFetching || !modelDraft.oauth_provider"
                  @click="fetchOAuthModels"
                >
                  <i class="fa-solid" :class="oauthModelsFetching ? 'fa-spinner fa-spin' : 'fa-magnifying-glass'"></i>
                  {{ oauthModelsFetching ? "查询中…" : "获取可用模型" }}
                </button>

                <NSelect
                  v-if="oauthAvailableModels.length > 0"
                  :value="oauthSelectedModelId"
                  class="settings-provider-select oauth-model-select"
                  menu-class="settings-provider-select-menu"
                  :options="oauthModelOptions"
                  placeholder="选择模型"
                  filterable
                  clearable
                  @update:value="onOAuthModelSelect"
                />
              </div>

              <p v-if="!oauthHasModelListing && !oauthAvailableModels.length" class="oauth-no-listing-hint">
                该提供商暂不支持自动模型列表，请在下方直接填写配置名称。
              </p>
            </div>

            <!-- 无模型列表或尚未拉取到列表时，需手动填写配置名称 -->
            <label v-if="showOAuthConfigNameField" class="full">
              <span>配置名称</span>
              <input
                v-model="modelDraft.model_name"
                type="text"
                placeholder="gpt-4o / gemini-2.0-flash"
              />
              <small>该提供商未提供模型列表或列表为空时，请在此填写在系统中使用的配置名称。</small>
            </label>
          </template>

          <label class="checkbox-row full">
            <input v-model="modelDraft.is_active" type="checkbox" />
            <span>保存后设为当前主模型</span>
          </label>
        </div>

        <!-- Capability overrides (API key mode only; hidden for OAuth to keep the form clean) -->
        <section v-if="!isOAuth" class="settings-capability-panel">
          <div
            class="settings-capability-panel__head"
            style="cursor: pointer; user-select: none;"
            @click="showCapabilities = !showCapabilities"
          >
            <div style="display: flex; align-items: flex-start; gap: 8px;">
              <i
                class="fa-solid"
                :class="showCapabilities ? 'fa-chevron-down' : 'fa-chevron-right'"
                style="margin-top: 4px;"
              ></i>
              <div>
                <strong>能力覆盖</strong>
                <p>默认根据供应商和协议推断能力；如果需要，可在当前模型上单独覆盖。</p>
              </div>
            </div>
            <label class="checkbox-row" @click.stop>
              <input v-model="modelDraft.use_provider_defaults" type="checkbox" />
              <span>跟随默认能力</span>
            </label>
          </div>

          <div v-show="showCapabilities" class="settings-capability-grid">
            <label
              v-for="option in capabilityOptions"
              :key="option.key"
              class="settings-capability-option"
              :class="{ 'is-disabled': modelDraft.use_provider_defaults }"
            >
              <input
                v-model="capabilityDraft[option.key]"
                type="checkbox"
                :disabled="modelDraft.use_provider_defaults"
              />
              <div>
                <strong>{{ option.label }}</strong>
                <small>{{ option.hint }}</small>
              </div>
            </label>
          </div>
        </section>

        <div class="settings-modal-actions">
          <button type="button" class="secondary-btn narrow" :disabled="saving" @click="closeEditorModal">取消</button>
          <button type="button" class="primary-btn narrow" :disabled="loading || saving" @click="saveModel">
            {{ isEditing ? "保存修改" : "保存模型配置" }}
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
/* ── 认证方式切换按钮 ─────────────────────────────────────────── */
.settings-auth-type-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.settings-auth-type-label {
  font-size: 13px;
  color: var(--muted);
  font-weight: 500;
}

.settings-auth-type-btns {
  display: flex;
  gap: 8px;
}

.settings-auth-type-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.settings-auth-type-btn:hover {
  border-color: var(--text);
  background: color-mix(in srgb, var(--text) 6%, transparent);
}

.settings-auth-type-btn.active {
  border-color: var(--text);
  background: color-mix(in srgb, var(--text) 10%, transparent);
  color: var(--text);
  font-weight: 600;
}

/* ── OAuth 提供商备注 ─────────────────────────────────────────── */
.oauth-provider-note {
  color: var(--muted);
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.5;
}

/* ── 步骤标签 ─────────────────────────────────────────────────── */
.oauth-step-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.oauth-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--text);
  color: var(--bg);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.oauth-step-done {
  color: var(--text);
  font-size: 14px;
}

/* ── 浏览器授权区域 ───────────────────────────────────────────── */
.oauth-launch-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: 8px;
}

/* ── 模型选择区域 ─────────────────────────────────────────────── */
.oauth-models-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.oauth-models-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.oauth-model-select {
  flex: 1;
  min-width: 200px;
}

.oauth-no-listing-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 0;
}

/* ── 操作按钮 ─────────────────────────────────────────────────── */
.oauth-launch-btn,
.oauth-fetch-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s, border-color 0.15s;
  white-space: nowrap;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  align-self: flex-start;
}

.oauth-launch-btn:hover:not(:disabled),
.oauth-fetch-btn:hover:not(:disabled) {
  border-color: var(--text);
  background: color-mix(in srgb, var(--text) 8%, transparent);
}

.oauth-launch-btn:disabled,
.oauth-fetch-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── 授权状态横幅 ─────────────────────────────────────────────── */
.oauth-token-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}

/* 等待中：静默灰 */
.oauth-token-pending {
  background: color-mix(in srgb, var(--muted) 8%, transparent);
  color: var(--muted);
  border: 1px solid var(--border);
}

/* 成功：深色强调 */
.oauth-token-ok {
  background: color-mix(in srgb, var(--text) 6%, transparent);
  color: var(--text);
  border: 1px solid var(--border-strong);
}

/* 失败：红色保留语义 */
.oauth-token-error {
  background: color-mix(in srgb, var(--red) 10%, transparent);
  color: var(--red);
  border: 1px solid color-mix(in srgb, var(--red) 30%, transparent);
}

.oauth-token-clear {
  margin-left: auto;
  background: transparent;
  border: none;
  color: inherit;
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
  opacity: 0.6;
  padding: 0;
}

.oauth-token-clear:hover {
  opacity: 1;
}

/* ── 环境变量提示 ─────────────────────────────────────────────── */
.oauth-env-hint {
  font-size: 12px;
  color: var(--muted);
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin: 0;
}

.oauth-env-hint code {
  background: var(--surface-muted);
  padding: 1px 4px;
  border-radius: 4px;
  font-family: monospace;
  color: var(--text);
}
</style>
