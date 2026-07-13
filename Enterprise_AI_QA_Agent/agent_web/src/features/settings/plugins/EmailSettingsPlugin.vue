<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useMessage } from "naive-ui";
import { api } from "../../../services/api";
import { t } from "../../../services/i18n";
import type { EmailConfigCreateRequest, EmailConfigPublic, MailboxProviderInfo } from "../../../types";

type Setup = {
  authorizationUrl: string;
  authStatus: string;
  authState: string;
  sessionId: string;
  polling: boolean;
  pollStartedAt: number;
};

const mailboxes = ref<EmailConfigPublic[]>([]);
const providers = ref<MailboxProviderInfo[]>([]);
const loading = ref(false);
const saving = ref(false);
const showCreate = ref(false);
const creatingMailbox = ref<EmailConfigPublic | null>(null);
const toast = useMessage();
const busy = ref<Record<string, boolean>>({});
const setupById = reactive<Record<number, Setup>>({});
const authPollTimers = new Map<number, number>();
const AUTH_POLL_INTERVAL_MS = 1500;
const AUTH_POLL_TIMEOUT_MS = 5 * 60 * 1000;
const draft = reactive({
  config_name: "", provider: "tencent_agently", sender_email: "", api_key: "",
  base_url: "", mailbox_id: "", routes_json: "", description: "", inbox_mode: "existing",
});

const providerMap = computed(() => new Map(providers.value.map((item) => [item.provider, item])));
const selectedProvider = computed(() => providerMap.value.get(draft.provider));
const isTencentDraft = computed(() => draft.provider === "tencent_agently");
const isOpenMailDraft = computed(() => draft.provider === "openmail");
const isRobotomailDraft = computed(() => draft.provider === "robotomail");
const supportsExistingMailboxBinding = computed(() => isOpenMailDraft.value || isRobotomailDraft.value);
const isBindingExistingMailbox = computed(() => supportsExistingMailboxBinding.value && draft.inbox_mode === "existing");
const mailboxNoun = computed(() => isOpenMailDraft.value ? "Inbox" : "Mailbox");
const existingMailboxAddressLabel = computed(() => isOpenMailDraft.value ? "已有 OpenMail 邮箱地址" : "已有 Robotomail 邮箱地址");
const bindingHint = computed(() => isOpenMailDraft.value
  ? "系统会从 OpenMail 查询这个已有 Inbox 并自动保存 Mailbox ID，不会创建新的 Inbox。"
  : "系统会从 Robotomail 查询这个已有 Mailbox 并自动保存 Mailbox ID，不会创建新的 Mailbox；mailbox-scoped API Key 可以使用此方式。");
const canProvisionDraft = computed(() => selectedProvider.value?.capabilities.includes("provision_inbox") === true);
const requiresRoutesDraft = computed(() => selectedProvider.value?.configuration_fields?.includes("routes") === true);

function setup(id: number) {
  return setupById[id] ||= {
    authorizationUrl: "",
    authStatus: t("nativeMailSettings.checking"),
    authState: "checking",
    sessionId: "",
    polling: false,
    pollStartedAt: 0,
  };
}
function message(type: "success" | "error", value: string) {
  toast[type](value, { duration: type === "success" ? 2600 : 4200 });
}
function providerName(key: string) { return providerMap.value.get(key)?.display_name || key; }
function key(id: number, action: string) { return `${id}:${action}`; }
function isBusy(id: number, action: string) { return Boolean(busy.value[key(id, action)]); }
async function action(id: number, name: string, fn: () => Promise<void>) {
  const actionKey = key(id, name);
  busy.value = { ...busy.value, [actionKey]: true };
  try { await fn(); }
  catch (error) { message("error", error instanceof Error ? error.message : "操作失败"); }
  finally { const next = { ...busy.value }; delete next[actionKey]; busy.value = next; }
}

async function loadSettings() {
  loading.value = true;
  try {
    const [configs, catalog] = await Promise.all([api.listEmailConfigs(), api.listMailProviders()]);
    mailboxes.value = configs;
    providers.value = catalog.providers;
    if (!providerMap.value.has(draft.provider)) draft.provider = providers.value[0]?.provider || "tencent_agently";
    for (const item of configs) void syncMailboxStatus(item);
  } catch (error) { message("error", error instanceof Error ? error.message : "加载邮箱失败"); }
  finally { loading.value = false; }
}

function openCreate() {
  creatingMailbox.value = null;
  Object.assign(draft, { config_name: "", provider: "tencent_agently", sender_email: "", api_key: "", base_url: "", mailbox_id: "", routes_json: "", description: "", inbox_mode: "existing" });
  showCreate.value = true;
}

async function createMailbox() {
  if (!draft.config_name.trim()) return message("error", "请输入配置名称");
  if (isBindingExistingMailbox.value && !draft.sender_email.trim()) {
    return message("error", `请输入要绑定的 ${draft.provider === "openmail" ? "OpenMail" : "Robotomail"} 邮箱地址`);
  }
  let routes: Record<string, string> | undefined;
  if (draft.routes_json.trim()) {
    try { routes = JSON.parse(draft.routes_json); }
    catch { return message("error", "路由映射必须是合法 JSON"); }
  }
  const extra_config: Record<string, unknown> = {};
  if (draft.base_url.trim()) extra_config.base_url = draft.base_url.trim();
  if (draft.mailbox_id.trim()) extra_config.mailbox_id = draft.mailbox_id.trim();
  if (routes) extra_config.routes = routes;
  const payload: EmailConfigCreateRequest = {
    config_name: draft.config_name.trim(), provider: draft.provider,
    sender_email: supportsExistingMailboxBinding.value && draft.inbox_mode === "create" ? "" : draft.sender_email.trim(),
    api_key: draft.api_key.trim() || null,
    enabled: false, is_default: false, description: draft.description.trim() || null, extra_config,
  };
  saving.value = true;
  let created: EmailConfigPublic | null = null;
  try {
    created = await api.createEmailConfig(payload);
    if (created.provider === "tencent_agently") {
      creatingMailbox.value = created;
      await startAuth(created);
      return;
    }
    const descriptor = providerMap.value.get(created.provider);
    if (!draft.mailbox_id.trim() && descriptor?.capabilities.includes("provision_inbox")) {
      const options = isBindingExistingMailbox.value
        ? { existing_email: draft.sender_email.trim() }
        : {};
      const provisioned = await api.mailProviderSetupAction(created.provider, "provision_inbox", {
        config_id: created.id,
        options,
      });
      if (provisioned.ok === false) throw new Error(String(provisioned.error || "创建厂商 Inbox 失败"));
    }
    const verified = await api.mailProviderSetupAction(created.provider, "status", { config_id: created.id });
    if (verified.ok !== true) throw new Error(String(verified.error || "厂商邮箱验证失败"));
    showCreate.value = false;
    message("success", `邮箱 ${String(verified.email || created.sender_email || created.config_name)} 已创建并验证`);
    await loadSettings();
  } catch (error) {
    if (created && created.provider !== "tencent_agently") {
      try { await api.deleteEmailConfig(created.id); }
      catch { /* Keep the original provider error as the actionable message. */ }
    }
    message("error", error instanceof Error ? error.message : "创建失败");
  }
  finally { saving.value = false; }
}

async function syncMailboxStatus(item: EmailConfigPublic) {
  const state = setup(item.id);
  state.authStatus = t("nativeMailSettings.checking");
  state.authState = "checking";
  try {
    const result = await api.mailProviderSetupAction(item.provider, "status", { config_id: item.id });
    applyConnectionResult(state, result);
  } catch (error) {
    state.authState = "failed";
    state.authStatus = error instanceof Error ? error.message : "状态检查失败";
  }
}

function applyConnectionResult(state: Setup, result: Record<string, unknown>) {
  const authState = String(result.auth_state || (result.ok === true ? "authorized" : "failed"));
  state.authState = authState;
  if (authState === "authorized" && result.ok === true) {
    state.authStatus = t("nativeMailSettings.available");
  } else if (authState === "reauth_required" || result.reauth_required === true) {
    state.authState = "reauth_required";
    state.authStatus = t("nativeMailSettings.auth_expired");
  } else if (authState === "authorizing") {
    state.authStatus = t("nativeMailSettings.authorizing");
  } else if (authState === "checking") {
    state.authStatus = t("nativeMailSettings.checking");
  } else {
    state.authStatus = String(result.error || result.auth_status || t("nativeMailSettings.unavailable"));
  }
}

async function testConnection(item: EmailConfigPublic) {
  await action(item.id, "test", async () => {
    const state = setup(item.id);
    state.authStatus = t("nativeMailSettings.checking");
    state.authState = "checking";
    const result = await api.mailProviderSetupAction(item.provider, "status", {
      config_id: item.id,
    });
    applyConnectionResult(state, result);
    if (result.ok !== true) {
      const error = state.authState === "reauth_required"
        ? t("nativeMailSettings.auth_expired_hint")
        : String(result.error || result.auth_status || "连接失败");
      throw new Error(`${item.config_name} 连接失败：${error}`);
    }
    const email = String(result.email || item.sender_email || "").trim();
    message("success", `${item.config_name}${email ? `（${email}）` : ""} 连接正常`);
  });
}

async function startAuth(item: EmailConfigPublic) {
  await action(item.id, "auth", async () => {
    stopAuthPolling(item.id);
    const result = await api.mailProviderSetupAction(item.provider, "auth_login", { config_id: item.id });
    if (result.ok === false) throw new Error(String(result.error || "启动授权失败"));
    const state = setup(item.id);
    state.authorizationUrl = String(result.authorization_url || "");
    state.sessionId = String(result.session_id || "");
    state.authStatus = String(result.status || "等待授权");
    state.authState = String(result.auth_state || "authorizing");
    state.pollStartedAt = Date.now();
    if (["authorized", "completed"].includes(state.authStatus)) {
      await completeAuth(item, state, String(result.email || ""));
      return;
    }
    state.polling = true;
    scheduleAuthPoll(item);
  });
}

function scheduleAuthPoll(item: EmailConfigPublic) {
  const existing = authPollTimers.get(item.id);
  if (existing !== undefined) window.clearTimeout(existing);
  const timer = window.setTimeout(() => {
    authPollTimers.delete(item.id);
    void pollAuth(item);
  }, AUTH_POLL_INTERVAL_MS);
  authPollTimers.set(item.id, timer);
}

function stopAuthPolling(id: number) {
  const timer = authPollTimers.get(id);
  if (timer !== undefined) window.clearTimeout(timer);
  authPollTimers.delete(id);
  if (setupById[id]) setupById[id].polling = false;
}

async function pollAuth(item: EmailConfigPublic) {
  const state = setup(item.id);
  if (!state.sessionId || !state.polling) return;
  if (Date.now() - state.pollStartedAt > AUTH_POLL_TIMEOUT_MS) {
    stopAuthPolling(item.id);
    state.authState = "failed";
    state.authStatus = "授权等待超时";
    message("error", "OAuth 授权等待超时，请重新开始授权");
    return;
  }
  try {
    const result = await api.mailProviderSetupAction(item.provider, "auth_login_status", { config_id: item.id, session_id: state.sessionId });
    if (!state.polling) return;
    if (result.ok === false || result.status === "failed") {
      state.authState = String(result.auth_state || "failed");
      state.authStatus = state.authState === "reauth_required"
        ? t("nativeMailSettings.auth_expired")
        : String(result.error || "OAuth 授权失败");
      throw new Error(String(result.error || "OAuth 授权失败"));
    }
    state.authStatus = String(result.status || "等待授权");
    state.authState = String(result.auth_state || "authorizing");
    state.authorizationUrl = String(result.authorization_url || state.authorizationUrl);
    if (["authorized", "completed"].includes(state.authStatus)) {
      stopAuthPolling(item.id);
      await completeAuth(item, state, String(result.email || ""));
      return;
    }
    scheduleAuthPoll(item);
  } catch (error) {
    stopAuthPolling(item.id);
    if (state.authState !== "reauth_required") {
      state.authState = "failed";
      state.authStatus = "授权检查失败";
    }
    message("error", error instanceof Error ? error.message : "OAuth 授权检查失败");
  }
}

async function completeAuth(item: EmailConfigPublic, state: Setup, verifiedEmail = "") {
  stopAuthPolling(item.id);
  const isCreating = creatingMailbox.value?.id === item.id;
  let email = verifiedEmail.trim();
  if (!email) {
    const result = await api.mailProviderSetupAction(item.provider, "status", { config_id: item.id });
    applyConnectionResult(state, result);
    if (result.ok !== true) throw new Error(String(result.error || "授权后的邮箱验证失败"));
    email = String(result.email || "").trim();
  }
  await persistIdentityEmail(item, email);
  state.authStatus = t("nativeMailSettings.available");
  state.authState = "authorized";
  state.authorizationUrl = "";
  state.sessionId = "";
  if (isCreating) {
    creatingMailbox.value = null;
    showCreate.value = false;
    await loadSettings();
  }
  message("success", email ? `邮箱 ${email} 已授权成功，可以正常使用` : t("nativeMailSettings.reauth_success"));
}

async function persistIdentityEmail(item: EmailConfigPublic, email: string): Promise<void> {
  if (email && email !== item.sender_email) {
    await api.updateEmailConfig(item.id, { config_name: item.config_name, provider: item.provider, sender_email: email, api_key: null, enabled: item.enabled, is_default: item.is_default, description: item.description || null, extra_config: {} });
    item.sender_email = email;
  }
}

async function cancelCreate() {
  if (saving.value) return;
  const pending = creatingMailbox.value;
  if (pending) {
    stopAuthPolling(pending.id);
    creatingMailbox.value = null;
    saving.value = true;
    try {
      await api.deleteEmailConfig(pending.id);
    } catch (error) {
      creatingMailbox.value = pending;
      message("error", error instanceof Error ? error.message : "取消创建失败");
      return;
    } finally {
      saving.value = false;
    }
  }
  showCreate.value = false;
}

async function activate(item: EmailConfigPublic) {
  await action(item.id, "activate", async () => { const result = await api.activateEmailConfig(item.id); message("success", result.message); await loadSettings(); });
}
async function remove(item: EmailConfigPublic) {
  const warning = item.enabled
    ? `确认删除当前邮箱 ${item.config_name}？删除后所有邮件工具将不可用，直到重新设置当前邮箱。`
    : `确认删除 ${item.config_name}？`;
  if (!window.confirm(warning)) return;
  await action(item.id, "delete", async () => { const result = await api.deleteEmailConfig(item.id); message("success", result.message); await loadSettings(); });
}
async function copyUrl(item: EmailConfigPublic) {
  await navigator.clipboard.writeText(setup(item.id).authorizationUrl);
  message("success", "授权链接已复制");
}

onMounted(loadSettings);
onBeforeUnmount(() => {
  for (const timer of authPollTimers.values()) window.clearTimeout(timer);
  authPollTimers.clear();
  const pending = creatingMailbox.value;
  if (pending) void api.deleteEmailConfig(pending.id);
});
</script>

<template>
  <section class="settings-pane settings-email-pane">
    <div class="settings-pane-head">
      <div>
        <h3>{{ t("nativeMailSettings.title") }}</h3>
        <p>{{ t("nativeMailSettings.desc") }}</p>
      </div>
    </div>

    <div class="settings-pane-block settings-model-grid-shell">
      <div v-if="loading" class="settings-empty">{{ t("nativeMailSettings.loading") }}</div>
      <div v-else class="settings-model-grid settings-email-grid">
        <article
          v-for="item in mailboxes"
          :key="item.id"
          class="settings-model-card settings-model-card-static settings-email-card"
          :class="{ active: item.enabled }"
        >
          <div class="settings-model-card__header">
            <span
              class="settings-model-card__badge"
              :class="item.enabled ? 'settings-model-card__badge-current' : 'settings-email-badge-idle'"
            >
              {{ item.enabled ? t("nativeMailSettings.current") : t("nativeMailSettings.inactive") }}
            </span>
          </div>

          <div class="settings-model-card__name settings-email-card__name">
            <span class="settings-email-card__icon"><i class="fa-regular fa-envelope"></i></span>
            <strong>{{ item.config_name }}</strong>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-building"></i>
            <span>{{ providerName(item.provider) }}</span>
          </div>
          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-key"></i>
            <span>{{ providerMap.get(item.provider)?.auth_type === "oauth_cli" ? "OAuth / CLI" : "API Key" }}</span>
          </div>

          <div class="settings-model-card__stats settings-model-card__stats-plain">
            <div class="settings-model-card__stat settings-model-card__stat-full">
              <span>{{ t("nativeMailSettings.email") }}</span>
              <strong :title="item.sender_email">{{ item.sender_email || t("nativeMailSettings.unbound") }}</strong>
            </div>
            <div class="settings-model-card__stat settings-model-card__stat-full">
              <span>{{ t("nativeMailSettings.status") }}</span>
              <strong :title="setup(item.id).authStatus">{{ setup(item.id).authStatus }}</strong>
            </div>
          </div>

          <div v-if="setup(item.id).authorizationUrl" class="settings-email-auth-box">
            <p>{{ t("nativeMailSettings.auth_prompt") }}</p>
            <code>{{ setup(item.id).authorizationUrl }}</code>
            <div class="settings-email-link-actions">
              <a class="primary-btn narrow" :href="setup(item.id).authorizationUrl" target="_blank" rel="noopener noreferrer">
                {{ t("nativeMailSettings.open_link") }}
              </a>
              <button type="button" class="secondary-btn narrow" @click="copyUrl(item)">{{ t("nativeMailSettings.copy") }}</button>
            </div>
            <span v-if="setup(item.id).polling" class="settings-email-polling">
              <i class="fa-solid fa-spinner fa-spin"></i> {{ t("nativeMailSettings.auto_detect") }}
            </span>
          </div>

          <div class="settings-model-card__spacer"></div>
          <div class="settings-model-card__actions">
            <button
              v-if="item.provider === 'tencent_agently' && setup(item.id).authState === 'reauth_required'"
              type="button"
              class="settings-model-card__action settings-model-card__action-edit"
              :disabled="isBusy(item.id, 'auth') || setup(item.id).polling"
              :title="t('nativeMailSettings.reauthorize')"
              :aria-label="t('nativeMailSettings.reauthorize')"
              @click="startAuth(item)"
            >
              <i class="fa-solid" :class="setup(item.id).polling ? 'fa-spinner fa-spin' : 'fa-arrow-rotate-right'"></i>
            </button>
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-test"
              :disabled="isBusy(item.id, 'test')"
              :title="t('nativeMailSettings.test')"
              :aria-label="t('nativeMailSettings.test')"
              @click="testConnection(item)"
            >
              <i class="fa-solid" :class="isBusy(item.id, 'test') ? 'fa-spinner fa-spin' : 'fa-plug-circle-check'"></i>
            </button>
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-activate"
              :disabled="item.enabled || isBusy(item.id, 'activate')"
              :title="t('nativeMailSettings.activate')"
              :aria-label="t('nativeMailSettings.activate')"
              @click="activate(item)"
            >
              <i class="fa-solid" :class="isBusy(item.id, 'activate') ? 'fa-spinner fa-spin' : 'fa-circle-check'"></i>
            </button>
            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-danger"
              :disabled="isBusy(item.id, 'delete')"
              :title="t('nativeMailSettings.delete')"
              :aria-label="t('nativeMailSettings.delete')"
              @click="remove(item)"
            >
              <i class="fa-solid" :class="isBusy(item.id, 'delete') ? 'fa-spinner fa-spin' : 'fa-trash-can'"></i>
            </button>
          </div>
        </article>

        <button
          type="button"
          class="settings-model-card settings-model-card-add settings-email-card settings-email-card-add"
          @click="openCreate"
        >
          <div class="settings-model-card-add__icon">+</div>
          <div class="settings-model-card-add__body">
            <strong>{{ t("nativeMailSettings.add") }}</strong>
            <p>{{ t("nativeMailSettings.add_desc") }}</p>
          </div>
        </button>
      </div>
      <div v-if="!loading && !mailboxes.length" class="settings-empty settings-email-empty">
        <strong>{{ t("nativeMailSettings.empty_title") }}</strong>
        <span>{{ t("nativeMailSettings.empty_desc") }}</span>
      </div>
    </div>

    <div v-if="showCreate" class="settings-modal-overlay" @click.self="cancelCreate">
      <form class="settings-modal-card settings-modal-card-clean settings-email-modal" @submit.prevent="createMailbox">
        <div class="settings-modal-head">
          <div>
            <h4>{{ creatingMailbox ? t("nativeMailSettings.creating_title") : t("nativeMailSettings.create_title") }}</h4>
            <p>{{ t("nativeMailSettings.create_desc") }}</p>
          </div>
          <button type="button" class="settings-modal-close" :disabled="saving" @click="cancelCreate">×</button>
        </div>

        <template v-if="!creatingMailbox">
          <div class="form-grid two">
            <label>
              <span>{{ t("nativeMailSettings.provider") }}</span>
              <select v-model="draft.provider"><option v-for="item in providers" :key="item.provider" :value="item.provider">{{ item.display_name }}</option></select>
            </label>
            <label>
              <span>{{ t("nativeMailSettings.config_name") }}</span>
              <input v-model="draft.config_name" :placeholder="t('nativeMailSettings.config_name_ph')" />
            </label>
            <template v-if="!isTencentDraft">
              <label class="full">
                <span>API Key</span>
                <input v-model="draft.api_key" type="password" autocomplete="new-password" :placeholder="t('nativeMailSettings.api_key_ph')" />
              </label>
              <label class="full">
                <span>API Base URL</span>
                <input v-model="draft.base_url" :placeholder="String(selectedProvider?.default_base_url || 'https://...')" />
              </label>
              <label v-if="supportsExistingMailboxBinding">
                <span>{{ mailboxNoun }} {{ t("nativeMailSettings.use_mode") }}</span>
                <select v-model="draft.inbox_mode">
                  <option value="existing">{{ t("nativeMailSettings.bind_existing") }} {{ mailboxNoun }}</option>
                  <option value="create">{{ t("nativeMailSettings.create_new") }} {{ mailboxNoun }}</option>
                </select>
              </label>
              <label v-if="!supportsExistingMailboxBinding">
                <span>Mailbox ID</span>
                <input v-model="draft.mailbox_id" :placeholder="canProvisionDraft ? t('nativeMailSettings.mailbox_id_optional') : t('nativeMailSettings.mailbox_id')" />
              </label>
              <label v-if="requiresRoutesDraft" class="full">
                <span>{{ t("nativeMailSettings.routes") }}</span>
                <textarea v-model="draft.routes_json" rows="5" placeholder='{"send":"/mailboxes/{mailbox_id}/messages","list":"/..."}'></textarea>
              </label>
              <label v-if="!supportsExistingMailboxBinding || isBindingExistingMailbox" class="full">
                <span>{{ supportsExistingMailboxBinding ? existingMailboxAddressLabel : t("nativeMailSettings.email") }}</span>
                <input v-model="draft.sender_email" :placeholder="isOpenMailDraft ? 'gleamopal4609@openmail.sh' : (isRobotomailDraft ? 'eighteen@robotomail.co' : t('nativeMailSettings.email_ph'))" />
              </label>
            </template>
            <label class="full">
              <span>{{ t("nativeMailSettings.description") }}</span>
              <textarea v-model="draft.description" rows="2" :placeholder="t('nativeMailSettings.optional')"></textarea>
            </label>
            <p class="settings-email-hint full">
              <i class="fa-solid fa-circle-info"></i>
              {{ isTencentDraft ? t("nativeMailSettings.tencent_hint") : (isBindingExistingMailbox ? bindingHint : (isRobotomailDraft ? t("nativeMailSettings.robot_create_hint") : (canProvisionDraft && !draft.mailbox_id.trim() ? t("nativeMailSettings.provision_hint") : t("nativeMailSettings.verify_hint")))) }}
            </p>
          </div>
          <div class="settings-modal-actions">
            <button type="button" class="secondary-btn narrow" :disabled="saving" @click="cancelCreate">{{ t("nativeMailSettings.cancel") }}</button>
            <button class="primary-btn narrow" type="submit" :disabled="saving">
              <i v-if="saving" class="fa-solid fa-spinner fa-spin"></i>
              {{ saving ? t("nativeMailSettings.processing") : (isTencentDraft ? t("nativeMailSettings.create_auth") : (isBindingExistingMailbox ? t("nativeMailSettings.bind_verify") : t("nativeMailSettings.create_verify"))) }}
            </button>
          </div>
        </template>

        <template v-else>
          <div class="settings-email-progress">
            <strong>{{ creatingMailbox.config_name }}</strong>
            <span>{{ t("nativeMailSettings.status") }}：{{ setup(creatingMailbox.id).authStatus }}</span>
            <template v-if="setup(creatingMailbox.id).authorizationUrl">
              <p>{{ t("nativeMailSettings.auth_prompt_auto") }}</p>
              <code>{{ setup(creatingMailbox.id).authorizationUrl }}</code>
              <div class="settings-email-link-actions">
                <a class="primary-btn narrow" :href="setup(creatingMailbox.id).authorizationUrl" target="_blank" rel="noopener noreferrer">{{ t("nativeMailSettings.open_auth") }}</a>
                <button type="button" class="secondary-btn narrow" @click="copyUrl(creatingMailbox)">{{ t("nativeMailSettings.copy_link") }}</button>
              </div>
            </template>
            <span v-if="setup(creatingMailbox.id).polling" class="settings-email-polling">
              <i class="fa-solid fa-spinner fa-spin"></i> {{ t("nativeMailSettings.auto_detect") }}
            </span>
          </div>
          <div class="settings-modal-actions">
            <button type="button" class="secondary-btn narrow" :disabled="saving" @click="cancelCreate">{{ t("nativeMailSettings.cancel_create") }}</button>
          </div>
        </template>
      </form>
    </div>
  </section>
</template>

<style scoped>
.settings-email-pane {
  color: var(--text);
  font-family: var(--app-font-family);
}

.settings-email-card {
  background: var(--surface);
}

.settings-email-card.active {
  border-color: color-mix(in srgb, var(--green) 58%, var(--border));
  box-shadow: 0 16px 36px color-mix(in srgb, var(--green) 14%, transparent);
}

.settings-email-badge-idle {
  background: var(--surface-muted);
  color: var(--muted);
}

.settings-email-card__name {
  display: flex;
  align-items: center;
  gap: 10px;
}

.settings-email-card__icon {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-soft);
  color: var(--text);
  display: grid;
  place-items: center;
}

.settings-email-auth-box,
.settings-email-progress {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-soft);
  color: var(--text);
}

.settings-email-auth-box p,
.settings-email-progress p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.65;
}

.settings-email-auth-box code,
.settings-email-progress code {
  display: block;
  max-height: 96px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--text);
  font-size: 12px;
}

.settings-email-link-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.settings-email-link-actions a {
  text-decoration: none;
}

.settings-email-polling {
  color: var(--blue);
  font-size: 12px;
}

.settings-email-empty {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-email-modal {
  width: min(680px, calc(100vw - 48px));
}

.settings-email-hint {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-soft);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.65;
}

.settings-email-hint i {
  margin-right: 6px;
  color: var(--blue);
}

@media (max-width: 720px) {
  .settings-email-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-email-card {
    width: 100%;
  }

  .form-grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
