<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../../../services/api";

interface ProviderInfo {
  provider: string;
  capabilities: string[];
  label: string;
  description: string;
  authType: string;
}

const PROVIDER_REGISTRY: ProviderInfo[] = [
  {
    provider: "tencent_agently",
    label: "Tencent Agent Mail",
    description: "CLI + OAuth, full mailbox capabilities",
    authType: "cli_oauth",
    capabilities: [],
  },
  {
    provider: "agentmail",
    label: "AgentMail",
    description: "REST API with inbox provisioning and webhooks",
    authType: "api_key",
    capabilities: [],
  },
  {
    provider: "robotomail",
    label: "Robotomail",
    description: "REST API with mailbox management and webhooks",
    authType: "api_key",
    capabilities: [],
  },
  {
    provider: "openmail",
    label: "OpenMail",
    description: "REST API with WebSocket support",
    authType: "api_key",
    capabilities: [],
  },
  {
    provider: "dead_simple_email",
    label: "Dead Simple Email",
    description: "REST API with IMAP/SMTP fallback",
    authType: "api_key",
    capabilities: [],
  },
  {
    provider: "agenticmail",
    label: "AgenticMail",
    description: "Self-hosted local API with MCP and SSE",
    authType: "local_api",
    capabilities: [],
  },
  {
    provider: "aws_agent_mailbox",
    label: "AWS Agent Mailbox",
    description: "HTTP API / MCP configuration-based",
    authType: "api_or_mcp",
    capabilities: [],
  },
];

const loading = ref(false);
const providers = ref<ProviderInfo[]>([...PROVIDER_REGISTRY]);
const selectedProvider = ref<string | null>(null);
const statusResults = ref<Record<string, Record<string, unknown>>>({});
const showConfigModal = ref(false);

const configDraft = ref({
  provider: "",
  config_name: "",
  api_key: "",
  sender_email: "",
  base_url: "",
  cli_path: "agently-cli",
  enabled: true,
  is_default: false,
});

const selectedProviderInfo = computed(() =>
  providers.value.find((p) => p.provider === selectedProvider.value)
);

async function loadProviders() {
  loading.value = true;
  try {
    const resp = await api.listMailProviders();
    if (resp.providers) {
      for (const remote of resp.providers) {
        const local = providers.value.find((p) => p.provider === remote.provider);
        if (local) {
          local.capabilities = remote.capabilities;
        }
      }
    }
  } catch {
    // backend may not be running
  } finally {
    loading.value = false;
  }
}

async function checkStatus(provider: string) {
  try {
    const result = await api.mailProviderStatus(provider);
    statusResults.value[provider] = result;
  } catch (e: any) {
    statusResults.value[provider] = { ok: false, error: e.message };
  }
}

function openConfigModal(provider: string) {
  const info = providers.value.find((p) => p.provider === provider);
  configDraft.value = {
    provider,
    config_name: info?.label || provider,
    api_key: "",
    sender_email: "",
    base_url: "",
    cli_path: "agently-cli",
    enabled: true,
    is_default: false,
  };
  showConfigModal.value = true;
}

async function saveConfig() {
  const draft = configDraft.value;
  const extra_config: Record<string, string> = {};
  if (draft.base_url) extra_config.base_url = draft.base_url;
  if (draft.cli_path && draft.cli_path !== "agently-cli") {
    extra_config.cli_path = draft.cli_path;
  }

  try {
    await api.createEmailConfig({
      config_name: draft.config_name,
      provider: draft.provider,
      api_key: draft.api_key || undefined,
      sender_email: draft.sender_email,
      enabled: draft.enabled,
      is_default: draft.is_default,
      extra_config,
    } as any);
    showConfigModal.value = false;
  } catch (e: any) {
    alert(e.message || "Failed to save");
  }
}

function closeModal() {
  showConfigModal.value = false;
}

onMounted(loadProviders);
</script>

<template>
  <section class="settings-pane">
    <div class="settings-pane-head">
      <h2>Agent Mailbox</h2>
      <p>Configure Agent Mailbox providers for sending, receiving, and managing emails.</p>
    </div>

    <div class="settings-model-grid settings-email-grid">
      <article
        v-for="info in providers"
        :key="info.provider"
        class="settings-model-card settings-email-card"
        @click="selectedProvider = info.provider"
      >
        <div class="settings-model-card__header">
          <span class="settings-model-card__badge">{{ info.authType }}</span>
        </div>
        <div class="settings-model-card__name">{{ info.label }}</div>
        <div class="settings-model-card__stat">{{ info.description }}</div>
        <div v-if="info.capabilities.length" class="settings-model-card__stat">
          {{ info.capabilities.join(", ") }}
        </div>
        <div class="settings-model-card__actions">
          <button class="settings-model-card__action" @click.stop="checkStatus(info.provider)">
            Status
          </button>
          <button class="settings-model-card__action" @click.stop="openConfigModal(info.provider)">
            Configure
          </button>
        </div>
        <div v-if="statusResults[info.provider]" class="settings-model-card__stat">
          <span :style="{ color: statusResults[info.provider].ok ? '#4caf50' : '#f44336' }">
            {{ statusResults[info.provider].ok ? "Connected" : statusResults[info.provider].error || "Error" }}
          </span>
        </div>
      </article>
    </div>

    <!-- Config Modal -->
    <div v-if="showConfigModal" class="settings-modal-overlay" @click.self="closeModal">
      <div class="settings-modal-card">
        <div class="settings-modal-head">
          <h3>Configure {{ selectedProviderInfo?.label || configDraft.provider }}</h3>
          <button class="settings-modal-close" @click="closeModal">X</button>
        </div>
        <div class="form-grid two">
          <label class="full">
            <span>Config Name</span>
            <input v-model="configDraft.config_name" type="text" />
          </label>
          <label v-if="selectedProviderInfo?.authType === 'api_key' || selectedProviderInfo?.authType === 'api_or_mcp'">
            <span>API Key</span>
            <input v-model="configDraft.api_key" type="password" />
          </label>
          <label v-if="selectedProviderInfo?.authType === 'cli_oauth'">
            <span>CLI Path</span>
            <input v-model="configDraft.cli_path" type="text" />
          </label>
          <label>
            <span>Sender Email</span>
            <input v-model="configDraft.sender_email" type="email" />
          </label>
          <label v-if="selectedProviderInfo?.authType !== 'cli_oauth'">
            <span>Base URL (optional)</span>
            <input v-model="configDraft.base_url" type="text" />
          </label>
          <label class="checkbox-row">
            <input v-model="configDraft.enabled" type="checkbox" />
            <span>Enabled</span>
          </label>
          <label class="checkbox-row">
            <input v-model="configDraft.is_default" type="checkbox" />
            <span>Set as Default</span>
          </label>
        </div>
        <div class="settings-modal-actions">
          <button class="secondary-btn narrow" @click="closeModal">Cancel</button>
          <button class="primary-btn narrow" @click="saveConfig">Save</button>
        </div>
      </div>
    </div>
  </section>
</template>
