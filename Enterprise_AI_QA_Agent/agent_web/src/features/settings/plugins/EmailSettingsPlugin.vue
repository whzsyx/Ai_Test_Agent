<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useMessage } from "naive-ui";
import { api } from "../../../services/api";
import type { EmailConfigCreateRequest, EmailConfigPublic, MailboxProviderInfo } from "../../../types";

type Setup = {
  authorizationUrl: string;
  authStatus: string;
  sessionId: string;
  polling: boolean;
  pollStartedAt: number;
};

const mailboxes = ref<EmailConfigPublic[]>([]);
const providers = ref<MailboxProviderInfo[]>([]);
const loading = ref(false);
const saving = ref(false);
const showCreate = ref(false);
const toast = useMessage();
const busy = ref<Record<string, boolean>>({});
const setupById = reactive<Record<number, Setup>>({});
const authPollTimers = new Map<number, number>();
const AUTH_POLL_INTERVAL_MS = 1500;
const AUTH_POLL_TIMEOUT_MS = 5 * 60 * 1000;
const draft = reactive({
  config_name: "", provider: "tencent_agently", sender_email: "", api_key: "",
  base_url: "", mailbox_id: "", routes_json: "", description: "",
});

const providerMap = computed(() => new Map(providers.value.map((item) => [item.provider, item])));
const selectedProvider = computed(() => providerMap.value.get(draft.provider));
const isTencentDraft = computed(() => draft.provider === "tencent_agently");
const isAgentMailDraft = computed(() => draft.provider === "agentmail");

function setup(id: number) {
  return setupById[id] ||= {
    authorizationUrl: "",
    authStatus: "未检查",
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
  } catch (error) { message("error", error instanceof Error ? error.message : "加载邮箱失败"); }
  finally { loading.value = false; }
}

function openCreate() {
  Object.assign(draft, { config_name: "", provider: "tencent_agently", sender_email: "", api_key: "", base_url: "", mailbox_id: "", routes_json: "", description: "" });
  showCreate.value = true;
}

async function createMailbox() {
  if (!draft.config_name.trim()) return message("error", "请输入配置名称");
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
    sender_email: draft.sender_email.trim(), api_key: draft.api_key.trim() || null,
    enabled: false, is_default: false, description: draft.description.trim() || null, extra_config,
  };
  saving.value = true;
  try {
    await api.createEmailConfig(payload);
    showCreate.value = false;
    message("success", "邮箱配置已创建。完成授权或连通性检查后，再设为全局当前邮箱。");
    await loadSettings();
  } catch (error) { message("error", error instanceof Error ? error.message : "创建失败"); }
  finally { saving.value = false; }
}

async function checkStatus(item: EmailConfigPublic) {
  await action(item.id, "status", async () => {
    const result = await api.mailProviderSetupAction(item.provider, item.provider === "tencent_agently" ? "auth_status" : "status", { config_id: item.id });
    const state = setup(item.id);
    if (item.provider === "tencent_agently") {
      if (result.logged_in !== true) {
        state.authStatus = String(result.auth_status || result.error || "未授权");
        throw new Error(state.authStatus);
      }
      await completeAuth(item, state);
      return;
    }
    state.authStatus = result.ok === true ? "可用" : String(result.error || "不可用");
    if (result.ok !== true) throw new Error(state.authStatus);
    message("success", `${item.config_name} 配置检查通过`);
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
    state.pollStartedAt = Date.now();
    if (["authorized", "completed"].includes(state.authStatus)) {
      await completeAuth(item, state);
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
    state.authStatus = "授权等待超时";
    message("error", "OAuth 授权等待超时，请重新开始授权");
    return;
  }
  try {
    const result = await api.mailProviderSetupAction(item.provider, "auth_login_status", { config_id: item.id, session_id: state.sessionId });
    if (result.ok === false || result.status === "failed") {
      throw new Error(String(result.error || "OAuth 授权失败"));
    }
    state.authStatus = String(result.status || "等待授权");
    state.authorizationUrl = String(result.authorization_url || state.authorizationUrl);
    if (["authorized", "completed"].includes(state.authStatus)) {
      stopAuthPolling(item.id);
      await completeAuth(item, state);
      return;
    }
    scheduleAuthPoll(item);
  } catch (error) {
    stopAuthPolling(item.id);
    state.authStatus = "授权检查失败";
    message("error", error instanceof Error ? error.message : "OAuth 授权检查失败");
  }
}

async function completeAuth(item: EmailConfigPublic, state: Setup) {
  stopAuthPolling(item.id);
  const email = await loadIdentity(item);
  state.authStatus = "可用";
  state.authorizationUrl = "";
  state.sessionId = "";
  message("success", email ? `邮箱 ${email} 已授权成功` : "邮箱已授权成功");
}

async function loadIdentity(item: EmailConfigPublic): Promise<string> {
  const result = await api.mailProviderSetupAction(item.provider, "whoami", { config_id: item.id });
  if (result.ok === false) throw new Error(String(result.error || "读取邮箱身份失败"));
  const email = String(result.email || (result.primary_alias as Record<string, unknown> | undefined)?.email || "").trim();
  setup(item.id).authStatus = "可用";
  if (email && email !== item.sender_email) {
    await api.updateEmailConfig(item.id, { config_name: item.config_name, provider: item.provider, sender_email: email, api_key: null, enabled: item.enabled, is_default: item.is_default, description: item.description || null, extra_config: {} });
    await loadSettings();
  }
  return email;
}

async function provision(item: EmailConfigPublic) {
  await action(item.id, "provision", async () => {
    const result = await api.mailProviderSetupAction(item.provider, "provision_inbox", { config_id: item.id, options: {} });
    if (result.ok === false) throw new Error(String(result.error || "创建厂商邮箱失败"));
    message("success", `厂商邮箱 ${String(result.email || result.mailbox_id || "")} 已创建`);
    await loadSettings();
  });
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
});
</script>

<template>
  <section class="mailbox-settings">
    <header class="page-header">
      <div><h2>Agent 原生邮箱</h2><p>全局统一管理各厂商 Agent Mail。所有 Agent 只使用当前激活邮箱。</p></div>
      <button class="primary" type="button" @click="openCreate">+ 新建邮箱</button>
    </header>
    <div v-if="loading" class="empty">正在加载邮箱...</div>
    <div v-else-if="!mailboxes.length" class="empty"><strong>还没有 Agent 邮箱</strong><span>新建配置、完成厂商授权，然后设为当前邮箱。</span></div>
    <div v-else class="mailbox-grid">
      <article v-for="item in mailboxes" :key="item.id" class="mailbox-card" :class="{ active: item.enabled }">
        <div class="card-top"><div class="mail-icon">✉</div><div><h3>{{ item.config_name }}</h3><p>{{ providerName(item.provider) }}</p></div><span class="state" :class="{ enabled: item.enabled }">{{ item.enabled ? "当前使用" : "未激活" }}</span></div>
        <dl>
          <div><dt>邮箱地址</dt><dd>{{ item.sender_email || "尚未生成或绑定" }}</dd></div>
          <div><dt>配置状态</dt><dd>{{ setup(item.id).authStatus }}</dd></div>
          <div><dt>认证方式</dt><dd>{{ providerMap.get(item.provider)?.auth_type === "oauth_cli" ? "OAuth / CLI" : "API Key" }}</dd></div>
        </dl>
        <div v-if="setup(item.id).authorizationUrl" class="auth-box"><p>请点击或复制以下链接在浏览器中完成授权：</p><code>{{ setup(item.id).authorizationUrl }}</code><div class="actions"><a :href="setup(item.id).authorizationUrl" target="_blank" rel="noopener noreferrer">打开链接</a><button type="button" @click="copyUrl(item)">复制</button><span v-if="setup(item.id).polling" class="polling-hint">正在自动检测授权结果...</span></div></div>
        <div class="actions wrap">
          <button v-if="item.provider === 'tencent_agently'" type="button" :disabled="isBusy(item.id, 'auth') || setup(item.id).polling" @click="startAuth(item)">{{ setup(item.id).polling ? "等待授权..." : "开始授权" }}</button>
          <button type="button" :disabled="isBusy(item.id, 'status')" @click="checkStatus(item)">检查配置</button>
          <button v-if="providerMap.get(item.provider)?.capabilities.includes('provision_inbox')" type="button" @click="provision(item)">创建厂商邮箱</button>
          <button v-if="!item.enabled" class="primary-outline" type="button" @click="activate(item)">设为当前</button>
          <button class="danger" type="button" @click="remove(item)">删除</button>
        </div>
      </article>
    </div>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false"><form class="modal" @submit.prevent="createMailbox">
      <h3>新建全局 Agent 邮箱</h3>
      <label>供应商<select v-model="draft.provider"><option v-for="item in providers" :key="item.provider" :value="item.provider">{{ item.display_name }}</option></select></label>
      <label>配置名称<input v-model="draft.config_name" placeholder="例如：备用 AgentMail" /></label>
      <template v-if="!isTencentDraft">
        <label>API Key<input v-model="draft.api_key" type="password" autocomplete="new-password" placeholder="保存在后端，不会回显" /></label>
        <label>API Base URL<input v-model="draft.base_url" :placeholder="String(selectedProvider?.default_base_url || 'https://...')" /></label>
        <label>Mailbox ID<input v-model="draft.mailbox_id" :placeholder="isAgentMailDraft ? '可留空，创建后再生成 Inbox' : '厂商邮箱 ID'" /></label>
        <label v-if="!isAgentMailDraft">路由映射 JSON<textarea v-model="draft.routes_json" rows="5" placeholder='{"send":"/mailboxes/{mailbox_id}/messages","list":"/..."}'></textarea></label>
      </template>
      <label>邮箱地址<input v-model="draft.sender_email" placeholder="授权或创建后可自动回填" /></label>
      <label>说明<textarea v-model="draft.description" rows="2" placeholder="可选"></textarea></label>
      <p class="hint">新建配置不会自动替换当前邮箱。确认新邮箱可用后，点击“设为当前”完成全局切换。</p>
      <div class="actions end"><button type="button" @click="showCreate = false">取消</button><button class="primary" type="submit" :disabled="saving">{{ saving ? "创建中..." : "创建配置" }}</button></div>
    </form></div>
  </section>
</template>

<style scoped>
.mailbox-settings{padding:24px 28px;color:var(--text-primary,#172033)}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;padding-bottom:20px;border-bottom:1px solid #e6eaf0}.page-header h2{margin:0 0 8px;font-size:22px}.page-header p,.card-top p{margin:0;color:#718096}button,select,input,textarea{font:inherit}button{border:1px solid #d8dee9;border-radius:9px;background:#fff;padding:9px 14px;cursor:pointer}button:disabled{opacity:.55;cursor:not-allowed}.primary{border-color:#4f7cff;background:#4f7cff;color:#fff}.primary-outline{border-color:#4f7cff;color:#315fd1}.danger{border-color:#ffd2d7;color:#d9364f;background:#fff6f7}.empty{margin-top:24px;min-height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;border:1px dashed #d8dee9;border-radius:14px;color:#718096}.mailbox-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:18px;margin-top:22px}.mailbox-card{border:1px solid #dfe5ee;border-radius:16px;padding:20px;background:#fff;box-shadow:0 8px 28px rgba(30,45,75,.05)}.mailbox-card.active{border-color:#88d9ae;box-shadow:0 8px 28px rgba(8,116,67,.1)}.card-top{display:flex;align-items:center;gap:12px}.card-top h3{margin:0 0 4px;font-size:17px}.mail-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:#edf3ff;color:#3f6be8;font-size:20px}.state{margin-left:auto;padding:4px 9px;border-radius:999px;background:#f1f3f6;color:#667085;font-size:12px}.state.enabled{background:#e9fbf1;color:#087443}dl{margin:18px 0;display:grid;gap:10px}dl div{display:grid;grid-template-columns:88px 1fr;gap:10px}dt{color:#8490a4}dd{margin:0;overflow-wrap:anywhere}.auth-box{margin:14px 0;padding:13px;border-radius:10px;background:#f7f9fc}.auth-box p{margin:0 0 8px}.auth-box code{display:block;max-height:90px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.polling-hint{color:#3867d6;font-size:13px}.actions{display:flex;align-items:center;gap:9px;margin-top:12px}.actions.wrap{flex-wrap:wrap}.actions.end{justify-content:flex-end}.actions a{color:#3867d6;text-decoration:none}.modal-mask{position:fixed;inset:0;z-index:40;display:grid;place-items:center;padding:20px;background:rgba(15,23,42,.44)}.modal{width:min(560px,100%);max-height:90vh;overflow:auto;padding:24px;border-radius:16px;background:#fff;box-shadow:0 24px 80px rgba(0,0,0,.2)}.modal h3{margin:0 0 20px}.modal label{display:grid;gap:7px;margin-bottom:15px;color:#4a5568}.modal input,.modal select,.modal textarea{width:100%;box-sizing:border-box;border:1px solid #d8dee9;border-radius:9px;padding:10px 11px;background:#fff}.hint{color:#718096;font-size:13px;line-height:1.6}@media(max-width:720px){.page-header{flex-direction:column}.mailbox-grid{grid-template-columns:1fr}.mailbox-settings{padding:18px}}
</style>
