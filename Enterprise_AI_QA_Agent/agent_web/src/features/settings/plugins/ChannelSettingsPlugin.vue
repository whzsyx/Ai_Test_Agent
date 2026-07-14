<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useMessage } from "naive-ui";
import * as QRCode from "qrcode";
import type { SettingsPluginDefinition } from "../plugins";
import {
  channelOrder,
  channelStrategies,
  createEmptyChannelForm,
  getChannelStrategy,
} from "../channelStrategies";
import type { ChannelForm } from "../channelStrategies";
import { api } from "../../../services/api";
import { t } from "../../../services/i18n";
import type {
  ChannelConfigPublic,
  ChannelDomain,
  ChannelPairingSessionPublic,
  ChannelStatus,
} from "../../../types";

defineProps<{
  plugin?: SettingsPluginDefinition;
}>();

const channels = channelOrder.map((domain) => channelStrategies[domain].definition);

const toast = useMessage();
const configs = ref<ChannelConfigPublic[]>([]);
const selectedDomain = ref<ChannelDomain>("qq");
const loading = ref(false);
const saving = ref(false);
const deleting = ref(false);
const pairing = ref(false);
const pairingSession = ref<ChannelPairingSessionPublic | null>(null);
const qrDataUrl = ref("");
const pairingPollTimer = ref<number | null>(null);
const form = reactive(createEmptyChannelForm());

const selectedStrategy = computed(() => getChannelStrategy(selectedDomain.value));
const selectedDefinition = computed(() => selectedStrategy.value.definition);
const selectedConfig = computed(() => configs.value.find((item) => item.domain === selectedDomain.value) || null);
const configByDomain = computed(() => new Map(configs.value.map((item) => [item.domain, item])));
const hasStoredSecret = computed(() => {
  const current = selectedConfig.value;
  if (!current) return false;
  return current.credential_fields?.[selectedDefinition.value.secretField] === true;
});
const canPairByQr = computed(() => selectedStrategy.value.supportsPairing);
const panelEyebrow = computed(() => t(selectedStrategy.value.panelEyebrowKey));
const manualFields = computed(() => selectedStrategy.value.manualFields(hasStoredSecret.value));
const pairedDevice = computed(() => {
  const value = selectedConfig.value?.public_config?.paired_device;
  return value === undefined || value === null ? "" : String(value);
});
const pairedAt = computed(() => {
  const value = selectedConfig.value?.public_config?.paired_at;
  return value === undefined || value === null ? "" : String(value);
});
const connectionSummaryItems = computed(() => {
  const config = selectedConfig.value;
  if (!config) return [];
  return [
    { labelKey: "channels.summary_channel", value: t(selectedDefinition.value.labelKey) },
    { labelKey: "channels.summary_remote_id", value: channelRemoteId(config), mono: true },
    { labelKey: "channels.summary_scope", value: t("channels.scope_global") },
    { labelKey: "channels.summary_status", value: statusLabel(config.domain, config) },
  ];
});
const credentialSummaryItems = computed(() => {
  const config = selectedConfig.value;
  if (!config) return [];
  const items: Array<{ labelKey: string; value: string; mono?: boolean }> = [];
  if (config.domain === "weixin") {
    items.push({ labelKey: "channels.summary_account_id", value: publicText(config, "account_id"), mono: true });
    items.push({ labelKey: "channels.summary_token", value: credentialLabel(config, "token") });
    items.push({ labelKey: "channels.summary_api_base", value: publicText(config, "api_base"), mono: true });
  } else {
    items.push({ labelKey: "channels.summary_app_id", value: publicText(config, "app_id"), mono: true });
    items.push({ labelKey: "channels.summary_secret", value: credentialLabel(config, "app_secret") });
    if (config.domain === "qq") {
      items.push({ labelKey: "channels.summary_sandbox", value: config.public_config?.sandbox_mode === true ? t("channels.yes") : t("channels.no") });
    } else {
      items.push({ labelKey: "channels.summary_connection_mode", value: connectionModeLabel(publicText(config, "connection_mode")) });
    }
  }
  items.push({ labelKey: "channels.summary_auth_method", value: authMethodLabel(publicText(config, "auth_method")) });
  items.push({ labelKey: "channels.summary_authorized_at", value: publicText(config, "paired_at") });
  return items;
});

function statusLabel(domain: ChannelDomain, config?: ChannelConfigPublic) {
  return getChannelStrategy(domain).statusLabel(config?.status);
}

function statusClass(status?: ChannelStatus) {
  return `is-${status || "unconfigured"}`;
}

function message(type: "success" | "error", value: string) {
  toast[type](value, { duration: type === "success" ? 2400 : 4200 });
}

function defaultName() {
  return selectedStrategy.value.defaultName();
}

function publicText(config: ChannelConfigPublic, key: string) {
  const value = config.public_config?.[key];
  const text = value === undefined || value === null ? "" : String(value).trim();
  return text || "-";
}

function channelRemoteId(config: ChannelConfigPublic) {
  const keys = ["remote_id", "user_id", "paired_device", "account_id"];
  for (const key of keys) {
    const value = publicText(config, key);
    if (value && value !== "-") return value;
  }
  return "-";
}

function credentialLabel(config: ChannelConfigPublic, key: string) {
  return config.credential_fields?.[key] === true ? t("channels.secret_saved") : t("channels.secret_missing");
}

function connectionModeLabel(value: string) {
  if (value === "websocket") return t("channels.mode_websocket");
  if (value === "webhook") return t("channels.mode_webhook");
  if (value === "reserved") return t("channels.mode_reserved");
  if (value === "event_callback") return t("channels.mode_event_callback");
  return value || "-";
}

function authMethodLabel(value: string) {
  if (value === "official_qr") return t("channels.auth_official_qr");
  if (value === "qr_pairing") return t("channels.auth_qr_pairing");
  return t("channels.auth_manual");
}

function getFieldValue(key: keyof ChannelForm) {
  const value = form[key];
  return value === undefined || value === null ? "" : String(value);
}

function getBooleanFieldValue(key: keyof ChannelForm) {
  return form[key] === true;
}

function readInputValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLSelectElement).value;
}

function readInputChecked(event: Event) {
  return (event.target as HTMLInputElement).checked;
}

function setFieldValue(key: keyof ChannelForm, value: string | boolean) {
  (form as Record<keyof ChannelForm, string | boolean>)[key] = value;
}

function applyConfigToForm() {
  selectedStrategy.value.applyConfig(form, selectedConfig.value);
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

function stopPairingPoll() {
  if (pairingPollTimer.value !== null) {
    window.clearTimeout(pairingPollTimer.value);
    pairingPollTimer.value = null;
  }
}

async function renderQr(payload: string) {
  if (payload.startsWith("data:image/")) {
    qrDataUrl.value = payload;
    return;
  }
  qrDataUrl.value = await QRCode.toDataURL(payload, {
    errorCorrectionLevel: "M",
    margin: 1,
    width: 240,
    color: { dark: "#0f172a", light: "#ffffff" },
  });
}

function schedulePairingPoll() {
  stopPairingPoll();
  const intervalSeconds = pairingSession.value?.interval || 3;
  pairingPollTimer.value = window.setTimeout(() => {
    pairingPollTimer.value = null;
    void pollPairing();
  }, Math.max(intervalSeconds, 2) * 1000);
}

async function startPairing() {
  if (!canPairByQr.value) {
    message("error", t("channels.qq_no_qr"));
    return;
  }
  pairing.value = true;
  stopPairingPoll();
  try {
    const session = await api.startChannelPairing(selectedDomain.value, {
      config_name: form.config_name.trim() || selectedStrategy.value.defaultName(),
      enabled: true,
      device_hint: "Mobile device",
    });
    pairingSession.value = session;
    await renderQr(session.qr_payload);
    schedulePairingPoll();
  } catch (error) {
    message("error", error instanceof Error ? error.message : t("channels.pairing_start_failed"));
  } finally {
    pairing.value = false;
  }
}

async function pollPairing() {
  const sessionId = pairingSession.value?.session_id;
  if (!sessionId) return;
  try {
    const session = await api.getChannelPairing(sessionId);
    pairingSession.value = session;
    if (session.status === "confirmed") {
      if (session.item) {
        configs.value = [
          ...configs.value.filter((item) => item.id !== session.item?.id && item.domain !== session.item?.domain),
          session.item,
        ];
        configs.value.sort((a, b) => channelOrder.indexOf(a.domain) - channelOrder.indexOf(b.domain));
        applyConfigToForm();
      }
      message("success", t("channels.pairing_confirmed_message"));
      stopPairingPoll();
      return;
    }
    if (session.status === "expired") {
      message("error", t("channels.pairing_expired_message"));
      stopPairingPoll();
      return;
    }
    schedulePairingPoll();
  } catch (error) {
    message("error", error instanceof Error ? error.message : t("channels.pairing_poll_failed"));
    stopPairingPoll();
  }
}

function buildPayload() {
  return selectedStrategy.value.buildPayload(form);
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
    configs.value.sort((a, b) => channelOrder.indexOf(a.domain) - channelOrder.indexOf(b.domain));
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

watch(selectedDomain, () => {
  stopPairingPoll();
  pairingSession.value = null;
  qrDataUrl.value = "";
  applyConfigToForm();
});
onMounted(loadSettings);
onBeforeUnmount(stopPairingPoll);
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
            <small>{{ statusLabel(item.domain, configByDomain.get(item.domain)) }}</small>
          </span>
          <em :class="statusClass(configByDomain.get(item.domain)?.status)"></em>
        </button>
      </aside>

      <div class="channel-settings__panel">
        <div class="channel-settings__panel-head">
          <div>
            <span class="channel-settings__eyebrow">{{ panelEyebrow }}</span>
            <h4>{{ t(selectedDefinition.labelKey) }}</h4>
            <p>{{ t(selectedDefinition.summaryKey) }}</p>
          </div>
          <span class="channel-settings__status" :class="statusClass(selectedConfig?.status)">
            {{ statusLabel(selectedDomain, selectedConfig) }}
          </span>
        </div>

        <div v-if="selectedConfig" class="channel-settings__connected">
          <section class="channel-settings__summary-card">
            <div class="channel-settings__summary-head">
              <strong>{{ t("channels.connection_summary") }}</strong>
              <small>{{ t("channels.summary_phase_hint") }}</small>
            </div>
            <div class="channel-settings__summary-grid">
              <div v-for="item in connectionSummaryItems" :key="item.labelKey" class="channel-settings__summary-item">
                <span>{{ t(item.labelKey) }}</span>
                <strong :class="{ 'is-mono': item.mono }">{{ item.value }}</strong>
              </div>
            </div>
          </section>

          <section class="channel-settings__summary-card">
            <div class="channel-settings__summary-head">
              <strong>{{ t("channels.credential_summary") }}</strong>
              <small>{{ t("channels.credential_summary_hint") }}</small>
            </div>
            <div class="channel-settings__summary-grid">
              <div v-for="item in credentialSummaryItems" :key="item.labelKey" class="channel-settings__summary-item">
                <span>{{ t(item.labelKey) }}</span>
                <strong :class="{ 'is-mono': item.mono }">{{ item.value }}</strong>
              </div>
            </div>
          </section>
        </div>

        <div v-if="canPairByQr" class="channel-settings__pairing">
          <div class="channel-settings__pairing-main">
            <strong>{{ t(selectedStrategy.pairingTitleKey) }}</strong>
            <p>{{ t(selectedStrategy.pairingDescriptionKey) }}</p>
            <div v-if="pairedDevice" class="channel-settings__paired">
              <i class="fa-solid fa-circle-check"></i>
              <span>{{ t("channels.bound_device", { device: pairedDevice }) }}</span>
              <small v-if="pairedAt">{{ pairedAt }}</small>
            </div>
            <button type="button" class="settings-model-card__action settings-model-card__action-activate" :disabled="pairing" @click="startPairing">
              <i class="fa-solid fa-qrcode"></i>
              <span>{{ pairing ? t("channels.qr_generating") : t("channels.qr_start") }}</span>
            </button>
          </div>

          <div class="channel-settings__qr-box" :class="{ 'is-empty': !qrDataUrl }">
            <img v-if="qrDataUrl" :src="qrDataUrl" :alt="t('channels.qr_alt')" />
            <div v-else>
              <i class="fa-solid fa-qrcode"></i>
              <span>{{ t("channels.qr_empty") }}</span>
            </div>
          </div>

          <div v-if="pairingSession" class="channel-settings__pairing-status">
            <span>{{ t("channels.pairing_status") }}：{{ t(`channels.pairing_${pairingSession.status}`) }}</span>
            <small v-if="pairingSession.message">{{ pairingSession.message }}</small>
            <a :href="pairingSession.pairing_url" target="_blank" rel="noreferrer">{{ t("channels.open_pairing_link") }}</a>
          </div>
        </div>

        <details class="channel-settings__advanced" :open="!canPairByQr">
          <summary>{{ t(selectedStrategy.manualSummaryKey) }}</summary>

          <div class="channel-settings__form">
            <label class="channel-settings__field">
              <span>{{ t("channels.config_name") }}</span>
              <input v-model="form.config_name" type="text" :placeholder="defaultName()" />
            </label>

            <label class="channel-settings__switch">
              <input v-model="form.enabled" type="checkbox" />
              <span>
                <strong>{{ t("channels.enabled_marker") }}</strong>
                <small>{{ t("channels.enabled_marker_desc") }}</small>
              </span>
            </label>

            <template v-for="field in manualFields" :key="field.key">
              <label v-if="field.kind === 'switch'" class="channel-settings__switch">
                <input
                  type="checkbox"
                  :checked="getBooleanFieldValue(field.key)"
                  @change="setFieldValue(field.key, readInputChecked($event))"
                />
                <span>
                  <strong>{{ t(field.labelKey) }}</strong>
                  <small>{{ t(field.hintKey) }}</small>
                </span>
              </label>

              <label v-else-if="field.kind === 'select'" class="channel-settings__field">
                <span>{{ t(field.labelKey) }}</span>
                <select :value="getFieldValue(field.key)" @change="setFieldValue(field.key, readInputValue($event))">
                  <option v-for="option in field.options" :key="option.value" :value="option.value">
                    {{ t(option.labelKey) }}
                  </option>
                </select>
              </label>

              <label v-else class="channel-settings__field">
                <span>{{ t(field.labelKey) }}</span>
                <input
                  :type="field.kind"
                  :value="getFieldValue(field.key)"
                  :autocomplete="field.autocomplete || undefined"
                  :placeholder="field.placeholder || ''"
                  @input="setFieldValue(field.key, readInputValue($event))"
                />
              </label>
            </template>

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
        </details>
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

.channel-settings__connected {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.channel-settings__summary-card {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface, #ffffff);
  padding: 14px;
}

.channel-settings__summary-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.channel-settings__summary-head strong {
  color: var(--text, #0f172a);
}

.channel-settings__summary-head small {
  color: var(--muted, #64748b);
  line-height: 1.45;
}

.channel-settings__summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.channel-settings__summary-item {
  min-width: 0;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface-muted, #f8fafc);
  padding: 10px 12px;
}

.channel-settings__summary-item span {
  display: block;
  margin-bottom: 6px;
  color: var(--muted, #64748b);
  font-size: 12px;
  font-weight: 700;
}

.channel-settings__summary-item strong {
  display: block;
  overflow: hidden;
  color: var(--text, #0f172a);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-settings__summary-item strong.is-mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.channel-settings__pairing {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 18px;
  align-items: center;
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.08), rgba(37, 99, 235, 0.03));
}

.channel-settings__pairing-main {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.channel-settings__pairing-main strong {
  color: var(--text, #0f172a);
  font-size: 18px;
}

.channel-settings__pairing-main p {
  max-width: 620px;
  margin: 0;
  color: var(--muted, #64748b);
  line-height: 1.6;
}

.channel-settings__paired {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: #15803d;
  font-weight: 700;
}

.channel-settings__paired small {
  color: var(--muted, #64748b);
  font-weight: 500;
}

.channel-settings__qr-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 240px;
  height: 240px;
  justify-self: end;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
}

.channel-settings__qr-box img {
  width: 220px;
  height: 220px;
}

.channel-settings__qr-box.is-empty {
  color: var(--muted, #64748b);
  background: rgba(255, 255, 255, 0.74);
}

.channel-settings__qr-box.is-empty div {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.channel-settings__qr-box.is-empty i {
  font-size: 42px;
  opacity: 0.45;
}

.channel-settings__pairing-status {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid rgba(37, 99, 235, 0.14);
  color: var(--text-secondary, #475569);
}

.channel-settings__pairing-status a {
  color: #2563eb;
  font-weight: 700;
  text-decoration: none;
}

.channel-settings__advanced {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface-muted, #f8fafc);
  padding: 0;
}

.channel-settings__advanced summary {
  cursor: pointer;
  padding: 13px 14px;
  color: var(--text, #0f172a);
  font-weight: 700;
}

.channel-settings__advanced .channel-settings__form {
  padding: 4px 14px 14px;
}

.channel-settings__advanced .channel-settings__actions {
  padding: 0 14px 14px;
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

  .channel-settings__connected,
  .channel-settings__summary-grid {
    grid-template-columns: 1fr;
  }

  .channel-settings__pairing {
    grid-template-columns: 1fr;
  }

  .channel-settings__qr-box {
    justify-self: stretch;
    width: 100%;
  }

  .channel-settings__panel-head,
  .channel-settings__actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
