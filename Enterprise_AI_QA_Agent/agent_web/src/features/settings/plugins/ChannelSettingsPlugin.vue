<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useMessage } from "naive-ui";
import type { SettingsPluginDefinition } from "../plugins";
import { api } from "../../../services/api";
import { t } from "../../../services/i18n";
import type {
  ChannelConfigCreateRequest,
  ChannelConfigPublic,
  ChannelDomain,
  ChannelProvider,
  ChannelStatus,
} from "../../../types";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();

type ChannelDefinition = {
  domain: ChannelDomain;
  provider: ChannelProvider;
  labelKey: string;
  summaryKey: string;
  icon: string;
  secretField: "app_secret" | "token";
};

const channels: ChannelDefinition[] = [
  { domain: "qq", provider: "qq", labelKey: "channels.qq", summaryKey: "channels.qq_desc", icon: "fa-brands fa-qq", secretField: "app_secret" },
  { domain: "feishu", provider: "feishu", labelKey: "channels.feishu", summaryKey: "channels.feishu_desc", icon: "fa-solid fa-paper-plane", secretField: "app_secret" },
  { domain: "lark", provider: "feishu", labelKey: "channels.lark", summaryKey: "channels.lark_desc", icon: "fa-solid fa-globe", secretField: "app_secret" },
  { domain: "weixin", provider: "weixin", labelKey: "channels.weixin", summaryKey: "channels.weixin_desc", icon: "fa-brands fa-weixin", secretField: "token" },
];

const toast = useMessage();
const configs = ref<ChannelConfigPublic[]>([]);
const selectedDomain = ref<ChannelDomain>("qq");
const loading = ref(false);
const saving = ref(false);
const deleting = ref(false);
const form = reactive({
  config_name: "",
  enabled: false,
  app_id: "",
  account_id: "",
  app_secret: "",
  token: "",
  sandbox_mode: false,
  connection_mode: "event_callback",
  description: "",
  clear_credentials: false,
});

const selectedDefinition = computed(() => channels.find((item) => item.domain === selectedDomain.value) || channels[0]);
const selectedConfig = computed(() => configs.value.find((item) => item.domain === selectedDomain.value) || null);
const configByDomain = computed(() => new Map(configs.value.map((item) => [item.domain, item])));
const hasStoredSecret = computed(() => {
  const current = selectedConfig.value;
  if (!current) return false;
  return current.credential_fields?.[selectedDefinition.value.secretField] === true;
});
const isWeixin = computed(() => selectedDomain.value === "weixin");
const isQq = computed(() => selectedDomain.value === "qq");
const isFeishuLike = computed(() => selectedDomain.value === "feishu" || selectedDomain.value === "lark");

function statusLabel(status?: ChannelStatus) {
  if (status === "configured") return t("channels.status_configured");
  if (status === "disabled") return t("channels.status_disabled");
  return t("channels.status_unconfigured");
}

function statusClass(status?: ChannelStatus) {
  return `is-${status || "unconfigured"}`;
}

function message(type: "success" | "error", value: string) {
  toast[type](value, { duration: type === "success" ? 2400 : 4200 });
}

function defaultName(definition: ChannelDefinition) {
  return `${t(definition.labelKey)} ${t("channels.config_suffix")}`;
}

function readText(config: ChannelConfigPublic | null, key: string) {
  const value = config?.public_config?.[key];
  return value === undefined || value === null ? "" : String(value);
}

function applyConfigToForm() {
  const definition = selectedDefinition.value;
  const config = selectedConfig.value;
  form.config_name = config?.config_name || defaultName(definition);
  form.enabled = config?.enabled || false;
  form.app_id = readText(config, "app_id");
  form.account_id = readText(config, "account_id");
  form.app_secret = "";
  form.token = "";
  form.sandbox_mode = config?.public_config?.sandbox_mode === true;
  form.connection_mode = readText(config, "connection_mode") || "event_callback";
  form.description = config?.description || "";
  form.clear_credentials = false;
}

async function loadSettings() {
  loading.value = true;
  try {
    configs.value = await api.listChannelConfigs();
    applyConfigToForm();
  } catch (error) {
    message("error", error instanceof Error ? error.message : t("channels.load_failed"));
  } finally {
    loading.value = false;
  }
}

function publicConfig(): Record<string, unknown> {
  if (isWeixin.value) {
    return { account_id: form.account_id.trim() };
  }
  if (isQq.value) {
    return { app_id: form.app_id.trim(), sandbox_mode: form.sandbox_mode };
  }
  return { app_id: form.app_id.trim(), connection_mode: form.connection_mode };
}

function credentials(): Record<string, string> | null {
  if (isWeixin.value) {
    return form.token.trim() ? { token: form.token.trim() } : null;
  }
  return form.app_secret.trim() ? { app_secret: form.app_secret.trim() } : null;
}

function buildPayload(): ChannelConfigCreateRequest {
  const definition = selectedDefinition.value;
  return {
    config_name: form.config_name.trim() || defaultName(definition),
    provider: definition.provider,
    domain: definition.domain,
    enabled: form.enabled,
    public_config: publicConfig(),
    credentials: credentials(),
    description: form.description.trim() || null,
  };
}

async function saveChannel() {
  saving.value = true;
  try {
    const current = selectedConfig.value;
    const payload = buildPayload();
    const saved = current
      ? await api.updateChannelConfig(current.id, { ...payload, clear_credentials: form.clear_credentials })
      : await api.createChannelConfig(payload);
    configs.value = [
      ...configs.value.filter((item) => item.id !== saved.id && item.domain !== saved.domain),
      saved,
    ];
    configs.value.sort((a, b) => channels.findIndex((item) => item.domain === a.domain) - channels.findIndex((item) => item.domain === b.domain));
    message("success", t("channels.save_success"));
    applyConfigToForm();
  } catch (error) {
    message("error", error instanceof Error ? error.message : t("channels.save_failed"));
  } finally {
    saving.value = false;
  }
}

async function deleteChannel() {
  const current = selectedConfig.value;
  if (!current) return;
  if (!window.confirm(t("channels.confirm_delete", { name: current.config_name }))) return;
  deleting.value = true;
  try {
    await api.deleteChannelConfig(current.id);
    configs.value = configs.value.filter((item) => item.id !== current.id);
    message("success", t("channels.delete_success"));
    applyConfigToForm();
  } catch (error) {
    message("error", error instanceof Error ? error.message : t("channels.delete_failed"));
  } finally {
    deleting.value = false;
  }
}

watch(selectedDomain, applyConfigToForm);
onMounted(loadSettings);
</script>

<template>
  <section class="settings-pane channel-settings">
    <div class="settings-pane-head">
      <div>
        <h3>{{ t("channels.title") }}</h3>
        <p>{{ t("channels.desc") }}</p>
      </div>
    </div>

    <div class="channel-settings__notice">
      <i class="fa-solid fa-circle-info"></i>
      <span>{{ t("channels.notice") }}</span>
    </div>

    <div class="channel-settings__layout">
      <aside class="channel-settings__rail" :aria-busy="loading">
        <button
          v-for="item in channels"
          :key="item.domain"
          type="button"
          class="channel-settings__channel"
          :class="{ active: selectedDomain === item.domain }"
          @click="selectedDomain = item.domain"
        >
          <i :class="item.icon"></i>
          <span>
            <strong>{{ t(item.labelKey) }}</strong>
            <small>{{ statusLabel(configByDomain.get(item.domain)?.status) }}</small>
          </span>
          <em :class="statusClass(configByDomain.get(item.domain)?.status)"></em>
        </button>
      </aside>

      <div class="channel-settings__panel">
        <div class="channel-settings__panel-head">
          <div>
            <span class="channel-settings__eyebrow">{{ t("channels.phase_one") }}</span>
            <h4>{{ t(selectedDefinition.labelKey) }}</h4>
            <p>{{ t(selectedDefinition.summaryKey) }}</p>
          </div>
          <span class="channel-settings__status" :class="statusClass(selectedConfig?.status)">
            {{ statusLabel(selectedConfig?.status) }}
          </span>
        </div>

        <div class="channel-settings__form">
          <label class="channel-settings__field">
            <span>{{ t("channels.config_name") }}</span>
            <input v-model="form.config_name" type="text" :placeholder="defaultName(selectedDefinition)" />
          </label>

          <label class="channel-settings__switch">
            <input v-model="form.enabled" type="checkbox" />
            <span>
              <strong>{{ t("channels.enabled_marker") }}</strong>
              <small>{{ t("channels.enabled_marker_desc") }}</small>
            </span>
          </label>

          <label v-if="isWeixin" class="channel-settings__field">
            <span>{{ t("channels.account_id") }}</span>
            <input v-model="form.account_id" type="text" placeholder="gh_xxxxxxxx" />
          </label>

          <label v-else class="channel-settings__field">
            <span>{{ t("channels.app_id") }}</span>
            <input v-model="form.app_id" type="text" placeholder="App ID" />
          </label>

          <label v-if="isQq" class="channel-settings__switch">
            <input v-model="form.sandbox_mode" type="checkbox" />
            <span>
              <strong>{{ t("channels.sandbox_mode") }}</strong>
              <small>{{ t("channels.sandbox_mode_desc") }}</small>
            </span>
          </label>

          <label v-if="isFeishuLike" class="channel-settings__field">
            <span>{{ t("channels.connection_mode") }}</span>
            <select v-model="form.connection_mode">
              <option value="event_callback">{{ t("channels.mode_event_callback") }}</option>
              <option value="webhook">{{ t("channels.mode_webhook") }}</option>
              <option value="reserved">{{ t("channels.mode_reserved") }}</option>
            </select>
          </label>

          <label class="channel-settings__field">
            <span>{{ isWeixin ? t("channels.token") : t("channels.app_secret") }}</span>
            <input
              v-if="isWeixin"
              v-model="form.token"
              type="password"
              autocomplete="new-password"
              :placeholder="hasStoredSecret ? t('channels.secret_saved_ph') : t('channels.secret_ph')"
            />
            <input
              v-else
              v-model="form.app_secret"
              type="password"
              autocomplete="new-password"
              :placeholder="hasStoredSecret ? t('channels.secret_saved_ph') : t('channels.secret_ph')"
            />
          </label>

          <label v-if="selectedConfig && hasStoredSecret" class="channel-settings__switch channel-settings__switch-danger">
            <input v-model="form.clear_credentials" type="checkbox" />
            <span>
              <strong>{{ t("channels.clear_credentials") }}</strong>
              <small>{{ t("channels.clear_credentials_desc") }}</small>
            </span>
          </label>

          <label class="channel-settings__field channel-settings__field-full">
            <span>{{ t("channels.description") }}</span>
            <textarea v-model="form.description" rows="3" :placeholder="t('channels.description_ph')"></textarea>
          </label>
        </div>

        <div class="channel-settings__actions">
          <button type="button" class="settings-model-card__action settings-model-card__action-activate" :disabled="saving" @click="saveChannel">
            <i class="fa-solid fa-floppy-disk"></i>
            <span>{{ saving ? t("channels.saving") : t("channels.save") }}</span>
          </button>
          <button
            v-if="selectedConfig"
            type="button"
            class="settings-model-card__action settings-model-card__action-danger"
            :disabled="deleting || saving"
            @click="deleteChannel"
          >
            <i class="fa-solid fa-trash-can"></i>
            <span>{{ deleting ? t("channels.deleting") : t("channels.delete") }}</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.channel-settings__notice {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 18px;
  padding: 12px 14px;
  border: 1px solid rgba(59, 130, 246, 0.24);
  border-radius: 8px;
  background: rgba(59, 130, 246, 0.08);
  color: var(--text-secondary, #475569);
  line-height: 1.55;
}

.channel-settings__notice i {
  margin-top: 3px;
  color: #2563eb;
}

.channel-settings__layout {
  display: grid;
  grid-template-columns: minmax(210px, 250px) minmax(0, 1fr);
  gap: 18px;
}

.channel-settings__rail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.channel-settings__channel {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 10px;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 72px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  color: var(--text, #0f172a);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

.channel-settings__channel:hover,
.channel-settings__channel.active {
  border-color: rgba(37, 99, 235, 0.42);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.channel-settings__channel i {
  display: inline-flex;
  justify-content: center;
  color: #2563eb;
  font-size: 18px;
}

.channel-settings__channel span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.channel-settings__channel strong,
.channel-settings__panel-head h4 {
  color: var(--text, #0f172a);
}

.channel-settings__channel small,
.channel-settings__panel-head p,
.channel-settings__field span,
.channel-settings__switch small {
  color: var(--muted, #64748b);
}

.channel-settings__channel em,
.channel-settings__status::before {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #94a3b8;
}

.channel-settings__channel em.is-configured,
.channel-settings__status.is-configured::before {
  background: #16a34a;
}

.channel-settings__channel em.is-disabled,
.channel-settings__status.is-disabled::before {
  background: #f59e0b;
}

.channel-settings__panel {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  padding: 18px;
}

.channel-settings__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.channel-settings__eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}

.channel-settings__panel-head h4 {
  margin: 0;
  font-size: 18px;
}

.channel-settings__panel-head p {
  max-width: 680px;
  margin: 6px 0 0;
  line-height: 1.55;
}

.channel-settings__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--surface-muted, #f8fafc);
  color: var(--text-secondary, #475569);
  font-size: 12px;
  font-weight: 700;
}

.channel-settings__status::before {
  content: "";
  display: inline-block;
}

.channel-settings__form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.channel-settings__field,
.channel-settings__switch {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.channel-settings__field-full {
  grid-column: 1 / -1;
}

.channel-settings__field input,
.channel-settings__field select,
.channel-settings__field textarea {
  width: 100%;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  color: var(--text, #0f172a);
  font: inherit;
  padding: 10px 12px;
  outline: none;
}

.channel-settings__field textarea {
  resize: vertical;
}

.channel-settings__field input:focus,
.channel-settings__field select:focus,
.channel-settings__field textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.channel-settings__switch {
  flex-direction: row;
  align-items: flex-start;
  min-height: 44px;
  padding: 11px 12px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface-muted, #f8fafc);
}

.channel-settings__switch input {
  margin-top: 3px;
}

.channel-settings__switch span {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.channel-settings__switch-danger {
  border-color: rgba(220, 38, 38, 0.24);
  background: rgba(220, 38, 38, 0.06);
}

.channel-settings__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

@media (max-width: 860px) {
  .channel-settings__layout {
    grid-template-columns: 1fr;
  }

  .channel-settings__rail {
    flex-direction: row;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .channel-settings__channel {
    min-width: 210px;
  }

  .channel-settings__form {
    grid-template-columns: 1fr;
  }

  .channel-settings__panel-head,
  .channel-settings__actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
