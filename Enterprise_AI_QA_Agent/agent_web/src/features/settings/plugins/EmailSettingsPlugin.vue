<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { NPopover, NSelect, type SelectOption } from "naive-ui";

import { api } from "../../../services/api";
import type { EmailConfigPublic, EmailConfigUpdateRequest } from "../../../types";

type EmailProvider = "aliyun" | "cybermail";
type MessageTone = "success" | "error";

interface ProviderGuide {
  label: string;
  title: string;
  description: string;
  requirements: string[];
  notes: string[];
  docs: Array<{ label: string; href: string }>;
}

const DEFAULT_ALIYUN_REGION = "cn-hangzhou";
const BUILTIN_PROVIDERS: EmailProvider[] = ["aliyun", "cybermail"];

const ALIYUN_SMTP_HOSTS: Record<string, string> = {
  "cn-hangzhou": "smtpdm.aliyun.com",
  "ap-southeast-1": "smtpdm-ap-southeast-1.aliyuncs.com",
  "us-east-1": "smtpdm-us-east-1.aliyuncs.com",
  "eu-central-1": "smtpdm-eu-central-1.aliyuncs.com",
};

const ALIYUN_REGION_OPTIONS: SelectOption[] = [
  { label: "中国（杭州）", value: "cn-hangzhou" },
  { label: "新加坡", value: "ap-southeast-1" },
  { label: "美国（弗吉尼亚）", value: "us-east-1" },
  { label: "德国（法兰克福）", value: "eu-central-1" },
];

const ALIYUN_PORT_OPTIONS: SelectOption[] = [
  { label: "465（SSL 直连，推荐）", value: 465 },
  { label: "80（普通 SMTP / STARTTLS）", value: 80 },
  { label: "25（普通 SMTP / STARTTLS）", value: 25 },
];

const CYBERMAIL_PORT_OPTIONS: SelectOption[] = [
  { label: "465（SSL）", value: 465 },
  { label: "587（提交端口）", value: 587 },
  { label: "25（内部中继）", value: 25 },
];

const PROVIDER_LABELS: Record<EmailProvider, string> = {
  aliyun: "阿里云邮件推送",
  cybermail: "CyberMail SMTP",
};

const PROVIDER_OPTIONS: SelectOption[] = BUILTIN_PROVIDERS.map((provider) => ({
  label: PROVIDER_LABELS[provider],
  value: provider,
}));

const PROVIDER_GUIDES: Record<EmailProvider, ProviderGuide> = {
  aliyun: {
    label: "阿里云",
    title: "DirectMail SMTP",
    description: "适合系统通知、告警和自动化结果投递，按阿里云 SMTP 发信方式配置。",
    requirements: [
      "先在阿里云 DirectMail 控制台完成发信域名和发信地址配置。",
      "SMTP 登录用户名使用完整发信地址。",
      "需要在发信地址里单独设置 SMTP 密码。",
    ],
    notes: [
      "区域会决定默认 SMTP Host。",
      "465 端口走 SSL，80 / 25 端口按普通 SMTP 连接。",
    ],
    docs: [
      { label: "通过 SMTP 发送邮件", href: "https://help.aliyun.com/zh/direct-mail/user-guide/send-emails-using-smtp" },
      { label: "SMTP Endpoint 列表", href: "https://help.aliyun.com/zh/direct-mail/smtp-endpoints" },
    ],
  },
  cybermail: {
    label: "CyberMail",
    title: "企业邮箱 SMTP",
    description: "适合已有企业邮箱系统接入，通常按企业管理员提供的 SMTP 域名配置。",
    requirements: [
      "外发通常需要填写 SMTP Host、端口、用户名和密码。",
      "如果走外部访问域名，一般要求 SMTP 认证。",
      "内部中继场景可按 MailGates 主机 + 25 端口配置。",
    ],
    notes: [
      "465 通常用于 SSL，587 常用于提交端口。",
      "不同企业实例的 SMTP Host 可能不同，请以管理员提供的信息为准。",
    ],
    docs: [
      {
        label: "他系统から SMTP 送信する設定",
        href: "https://cloud-sup.cybersolutions.co.jp/hc/ja/articles/360039314431-%E4%BB%96%E3%82%B7%E3%82%B9%E3%83%86%E3%83%A0%E3%81%8B%E3%82%89SMTP%E9%80%81%E4%BF%A1%E3%81%99%E3%82%8B%E8%A8%AD%E5%AE%9A",
      },
    ],
  },
};

const loading = ref(false);
const saving = ref(false);
const showEditorModal = ref(false);
const isCreateMode = ref(false);
const editingProvider = ref<EmailProvider>("aliyun");
const busyActionKey = ref("");
const emailConfigs = ref<EmailConfigPublic[]>([]);
const messageVisible = ref(false);
const messageText = ref("");
const messageTone = ref<MessageTone>("success");
let messageTimer: ReturnType<typeof setTimeout> | null = null;

const aliyunDraft = reactive<EmailConfigUpdateRequest>({
  provider: "aliyun",
  enabled: false,
  is_default: false,
  from_email: "",
  from_name: "",
  reply_to: "",
  region: DEFAULT_ALIYUN_REGION,
  smtp_host: "",
  smtp_port: 465,
  smtp_username: "",
  smtp_password: "",
  access_key_id: null,
  access_key_secret: null,
  account_name: null,
  use_tls: true,
});

const cybermailDraft = reactive<EmailConfigUpdateRequest>({
  provider: "cybermail",
  enabled: false,
  is_default: false,
  from_email: "",
  from_name: "",
  reply_to: "",
  region: null,
  smtp_host: "",
  smtp_port: 465,
  smtp_username: "",
  smtp_password: "",
  access_key_id: null,
  access_key_secret: null,
  account_name: null,
  use_tls: true,
});

const existingProviders = computed(() => new Set(emailConfigs.value.map((item) => item.provider)));
const availableProviders = computed<SelectOption[]>(() =>
  PROVIDER_OPTIONS.filter((option) => !existingProviders.value.has(option.value as EmailProvider)),
);
const activeGuide = computed(() => PROVIDER_GUIDES[editingProvider.value]);
const aliyunResolvedHost = computed(() => resolveAliyunHost(aliyunDraft.region));

onMounted(() => {
  void loadSettings();
});

onBeforeUnmount(() => {
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
});

async function loadSettings() {
  loading.value = true;
  try {
    emailConfigs.value = await api.listEmailConfigs();
    hydrateEmailDrafts(emailConfigs.value);
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "加载邮件设置失败。");
  } finally {
    loading.value = false;
  }
}

function showMessage(tone: MessageTone, text: string) {
  messageTone.value = tone;
  messageText.value = text;
  messageVisible.value = true;

  if (messageTimer) {
    clearTimeout(messageTimer);
  }

  messageTimer = setTimeout(() => {
    messageVisible.value = false;
    messageTimer = null;
  }, 2600);
}

function resolveAliyunHost(region?: string | null) {
  const normalized = (region ?? "").trim() || DEFAULT_ALIYUN_REGION;
  return ALIYUN_SMTP_HOSTS[normalized] ?? ALIYUN_SMTP_HOSTS[DEFAULT_ALIYUN_REGION];
}

function hydrateEmailDrafts(items: EmailConfigPublic[]) {
  const aliyun = items.find((item) => item.provider === "aliyun");
  if (aliyun) {
    aliyunDraft.enabled = aliyun.enabled;
    aliyunDraft.is_default = aliyun.is_default;
    aliyunDraft.from_email = aliyun.from_email;
    aliyunDraft.from_name = aliyun.from_name;
    aliyunDraft.reply_to = aliyun.reply_to;
    aliyunDraft.region = aliyun.region ?? DEFAULT_ALIYUN_REGION;
    aliyunDraft.smtp_host = aliyun.smtp_host ?? resolveAliyunHost(aliyun.region);
    aliyunDraft.smtp_port = aliyun.smtp_port ?? 465;
    aliyunDraft.smtp_username = aliyun.smtp_username ?? aliyun.from_email ?? "";
    aliyunDraft.smtp_password = "";
    aliyunDraft.use_tls = aliyun.smtp_port === 465;
  }

  const cybermail = items.find((item) => item.provider === "cybermail");
  if (cybermail) {
    cybermailDraft.enabled = cybermail.enabled;
    cybermailDraft.is_default = cybermail.is_default;
    cybermailDraft.from_email = cybermail.from_email;
    cybermailDraft.from_name = cybermail.from_name;
    cybermailDraft.reply_to = cybermail.reply_to;
    cybermailDraft.smtp_host = cybermail.smtp_host ?? "";
    cybermailDraft.smtp_port = cybermail.smtp_port ?? 465;
    cybermailDraft.smtp_username = cybermail.smtp_username ?? "";
    cybermailDraft.smtp_password = "";
    cybermailDraft.use_tls = cybermail.smtp_port === 465 ? true : cybermail.use_tls;
  }
}

function resetDraft(provider: EmailProvider) {
  if (provider === "aliyun") {
    aliyunDraft.provider = "aliyun";
    aliyunDraft.enabled = false;
    aliyunDraft.is_default = false;
    aliyunDraft.from_email = "";
    aliyunDraft.from_name = "";
    aliyunDraft.reply_to = "";
    aliyunDraft.region = DEFAULT_ALIYUN_REGION;
    aliyunDraft.smtp_host = resolveAliyunHost(DEFAULT_ALIYUN_REGION);
    aliyunDraft.smtp_port = 465;
    aliyunDraft.smtp_username = "";
    aliyunDraft.smtp_password = "";
    aliyunDraft.use_tls = true;
    return;
  }

  cybermailDraft.provider = "cybermail";
  cybermailDraft.enabled = false;
  cybermailDraft.is_default = false;
  cybermailDraft.from_email = "";
  cybermailDraft.from_name = "";
  cybermailDraft.reply_to = "";
  cybermailDraft.smtp_host = "";
  cybermailDraft.smtp_port = 465;
  cybermailDraft.smtp_username = "";
  cybermailDraft.smtp_password = "";
  cybermailDraft.use_tls = true;
}

function describeChannel(item: EmailConfigPublic) {
  if (item.provider === "aliyun") {
    const region = item.region || DEFAULT_ALIYUN_REGION;
    const host = item.smtp_host || resolveAliyunHost(region);
    const port = item.smtp_port || 465;
    return `${region} / ${host}:${port}`;
  }
  const host = item.smtp_host || "未填写 SMTP Host";
  const port = item.smtp_port || 465;
  return `${host}:${port}`;
}

function describeSecret(item: EmailConfigPublic) {
  if (item.provider === "aliyun") {
    return item.has_smtp_password ? "SMTP 密码已配置" : "SMTP 密码未配置";
  }
  return item.has_smtp_password ? "SMTP 认证已配置" : "SMTP 认证未配置";
}

function openCreateModal() {
  if (!availableProviders.value.length) {
    showMessage("error", "当前内置邮件通道已全部创建，请直接编辑现有卡片。");
    return;
  }

  isCreateMode.value = true;
  editingProvider.value = availableProviders.value[0].value as EmailProvider;
  resetDraft(editingProvider.value);
  showEditorModal.value = true;
}

function openEditModal(provider: EmailProvider) {
  isCreateMode.value = false;
  editingProvider.value = provider;
  showEditorModal.value = true;
}

function closeEditorModal() {
  showEditorModal.value = false;
}

function actionKey(provider: EmailProvider, action: string) {
  return `${provider}:${action}`;
}

async function withAction(provider: EmailProvider, action: string, runner: () => Promise<void>) {
  busyActionKey.value = actionKey(provider, action);
  try {
    await runner();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "邮件配置操作失败。");
  } finally {
    busyActionKey.value = "";
  }
}

async function testConnection(item: EmailConfigPublic) {
  await withAction(item.provider, "test", async () => {
    const result = await api.testEmailConfigConnection(item.provider);
    if (result.ok) {
      if (result.preview) {
        showMessage("success", `连接测试成功：${PROVIDER_LABELS[item.provider]}，${result.preview}`);
      } else {
        showMessage("success", `连接测试成功：${PROVIDER_LABELS[item.provider]}`);
      }
      return;
    }
    showMessage("error", `连接测试失败：${PROVIDER_LABELS[item.provider]}`);
  });
}

async function activateChannel(item: EmailConfigPublic) {
  await withAction(item.provider, "activate", async () => {
    await api.activateEmailConfig(item.provider);
    showMessage("success", `已启用并设为默认通道：${PROVIDER_LABELS[item.provider]}`);
    await loadSettings();
  });
}

async function deleteChannel(item: EmailConfigPublic) {
  const confirmed = window.confirm(`确定删除邮件通道“${PROVIDER_LABELS[item.provider]}”吗？`);
  if (!confirmed) {
    return;
  }

  await withAction(item.provider, "delete", async () => {
    await api.deleteEmailConfig(item.provider);
    showMessage("success", `已删除邮件通道：${PROVIDER_LABELS[item.provider]}`);
    await loadSettings();
  });
}

function buildAliyunPayload(): EmailConfigUpdateRequest {
  const region = (aliyunDraft.region ?? "").trim() || DEFAULT_ALIYUN_REGION;
  const port = Number(aliyunDraft.smtp_port || 465);
  const fromEmail = aliyunDraft.from_email.trim();

  return {
    provider: "aliyun",
    enabled: aliyunDraft.enabled,
    is_default: aliyunDraft.is_default,
    from_email: fromEmail,
    from_name: aliyunDraft.from_name.trim(),
    reply_to: aliyunDraft.reply_to.trim(),
    access_key_id: null,
    access_key_secret: null,
    account_name: null,
    region,
    smtp_host: resolveAliyunHost(region),
    smtp_port: port,
    smtp_username: fromEmail || null,
    smtp_password: aliyunDraft.smtp_password.trim() || null,
    use_tls: port === 465,
  };
}

function buildCyberMailPayload(): EmailConfigUpdateRequest {
  const port = Number(cybermailDraft.smtp_port || 465);

  return {
    provider: "cybermail",
    enabled: cybermailDraft.enabled,
    is_default: cybermailDraft.is_default,
    from_email: cybermailDraft.from_email.trim(),
    from_name: cybermailDraft.from_name.trim(),
    reply_to: cybermailDraft.reply_to.trim(),
    access_key_id: null,
    access_key_secret: null,
    account_name: null,
    region: null,
    smtp_host: cybermailDraft.smtp_host.trim() || null,
    smtp_port: port,
    smtp_username: cybermailDraft.smtp_username.trim() || null,
    smtp_password: cybermailDraft.smtp_password.trim() || null,
    use_tls: port === 465,
  };
}

async function saveEmail() {
  saving.value = true;
  try {
    const payload = editingProvider.value === "aliyun" ? buildAliyunPayload() : buildCyberMailPayload();
    const saved = await api.updateEmailConfig(payload);
    showMessage("success", `${isCreateMode.value ? "已新增" : "已保存"}：${PROVIDER_LABELS[saved.provider]}`);
    closeEditorModal();
    await loadSettings();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : "保存邮件配置失败。");
  } finally {
    saving.value = false;
  }
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
        <h3>邮件设置</h3>
        <p>卡片里直接完成新增、删除、启用、测试和编辑配置。</p>
      </div>
    </div>

    <div class="settings-pane-block settings-model-grid-shell">
      <div class="settings-model-grid">
        <article
          v-for="item in emailConfigs"
          :key="item.provider"
          class="settings-model-card settings-model-card-static"
        >
          <div class="settings-model-card__header">
            <span class="settings-model-card__badge" :class="item.enabled ? 'settings-model-card__badge-current' : ''">
              {{ item.enabled ? "已启用" : "已停用" }}
            </span>
            <span v-if="item.is_default" class="settings-model-card__badge settings-model-card__badge-current">
              默认通道
            </span>
          </div>

          <div class="settings-model-card__name">
            <strong>{{ PROVIDER_LABELS[item.provider] }}</strong>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-envelope"></i>
            <span>{{ item.from_email || "尚未配置发信地址" }}</span>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-server"></i>
            <span>{{ describeChannel(item) }}</span>
          </div>

          <div class="settings-model-card__stats settings-model-card__stats-plain">
            <div class="settings-model-card__stat settings-model-card__stat-full">
              <span>认证状态</span>
              <strong>{{ describeSecret(item) }}</strong>
            </div>
            <div class="settings-model-card__stat settings-model-card__stat-full">
              <span>发件人名称</span>
              <strong>{{ item.from_name || "未设置" }}</strong>
            </div>
          </div>

          <div class="settings-model-card__spacer"></div>

          <div class="settings-model-card__actions">
            <NPopover trigger="hover" placement="top" :show-arrow="true">
              <template #trigger>
                <button type="button" class="settings-model-card__action settings-model-card__action-test" title="查看说明">
                  <i class="fa-solid fa-circle-info"></i>
                </button>
              </template>
              <div class="settings-email-popover">
                <strong>{{ PROVIDER_GUIDES[item.provider].title }}</strong>
                <p>{{ PROVIDER_GUIDES[item.provider].description }}</p>
                <ul>
                  <li v-for="note in PROVIDER_GUIDES[item.provider].requirements" :key="note">{{ note }}</li>
                </ul>
              </div>
            </NPopover>

            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-test"
              :disabled="busyActionKey === actionKey(item.provider, 'test')"
              title="测试连接"
              @click="testConnection(item)"
            >
              <i
                class="fa-solid"
                :class="busyActionKey === actionKey(item.provider, 'test') ? 'fa-spinner fa-spin' : 'fa-plug-circle-check'"
              ></i>
            </button>

            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-activate"
              :disabled="(item.enabled && item.is_default) || busyActionKey === actionKey(item.provider, 'activate')"
              title="启用并设为默认"
              @click="activateChannel(item)"
            >
              <i
                class="fa-solid"
                :class="busyActionKey === actionKey(item.provider, 'activate') ? 'fa-spinner fa-spin' : 'fa-circle-check'"
              ></i>
            </button>

            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-edit"
              title="编辑配置"
              @click="openEditModal(item.provider)"
            >
              <i class="fa-solid fa-pen-to-square"></i>
            </button>

            <button
              type="button"
              class="settings-model-card__action settings-model-card__action-danger"
              :disabled="busyActionKey === actionKey(item.provider, 'delete')"
              title="删除通道"
              @click="deleteChannel(item)"
            >
              <i
                class="fa-solid"
                :class="busyActionKey === actionKey(item.provider, 'delete') ? 'fa-spinner fa-spin' : 'fa-trash-can'"
              ></i>
            </button>
          </div>
        </article>

        <button type="button" class="settings-model-card settings-model-card-add" @click="openCreateModal">
          <div class="settings-model-card-add__icon">+</div>
          <div class="settings-model-card-add__body">
            <strong>新增邮件通道</strong>
            <p>
              {{ availableProviders.length ? "创建新的邮件推送配置" : "当前内置邮件提供商已全部创建" }}
            </p>
          </div>
        </button>
      </div>
    </div>

    <div v-if="showEditorModal" class="settings-modal-overlay" @click.self="closeEditorModal">
      <section class="settings-modal-card settings-modal-card-clean">
        <div class="settings-modal-head">
          <div>
            <h4>{{ isCreateMode ? "新增邮件通道" : PROVIDER_LABELS[editingProvider] }}</h4>
            <p>{{ isCreateMode ? "创建新的邮件推送配置" : "修改当前邮件推送配置" }}</p>
          </div>
          <button type="button" class="settings-modal-close" @click="closeEditorModal">×</button>
        </div>

        <div class="settings-email-modal-tip">
          <NPopover trigger="hover" placement="bottom-start" :show-arrow="true">
            <template #trigger>
              <button type="button" class="settings-email-tip-btn">
                <i class="fa-solid fa-circle-info"></i>
                <span>配置说明</span>
              </button>
            </template>
            <div class="settings-email-popover settings-email-popover-wide">
              <strong>{{ activeGuide.title }}</strong>
              <p>{{ activeGuide.description }}</p>
              <ul>
                <li v-for="item in activeGuide.requirements" :key="item">{{ item }}</li>
              </ul>
              <ul>
                <li v-for="item in activeGuide.notes" :key="item">{{ item }}</li>
              </ul>
              <div class="settings-email-docs">
                <a v-for="doc in activeGuide.docs" :key="doc.href" :href="doc.href" target="_blank" rel="noreferrer">
                  {{ doc.label }}
                </a>
              </div>
            </div>
          </NPopover>
        </div>

        <div class="form-grid two">
          <label v-if="isCreateMode" class="full">
            <span>提供商</span>
            <NSelect
              v-model:value="editingProvider"
              class="settings-provider-select"
              :options="availableProviders"
              :consistent-menu-width="false"
            />
          </label>

          <template v-if="editingProvider === 'aliyun'">
            <label>
              <span>发信区域</span>
              <NSelect
                v-model:value="aliyunDraft.region"
                class="settings-provider-select"
                :options="ALIYUN_REGION_OPTIONS"
                :consistent-menu-width="false"
              />
            </label>

            <label>
              <span>SMTP 服务地址</span>
              <input :value="aliyunResolvedHost" type="text" readonly class="settings-readonly-input" />
            </label>

            <label>
              <span>SMTP 端口</span>
              <NSelect
                v-model:value="aliyunDraft.smtp_port"
                class="settings-provider-select"
                :options="ALIYUN_PORT_OPTIONS"
                :consistent-menu-width="false"
              />
            </label>

            <label>
              <span>发信地址</span>
              <input v-model="aliyunDraft.from_email" type="email" placeholder="notice@example.com" />
            </label>

            <label>
              <span>SMTP 密码</span>
              <input v-model="aliyunDraft.smtp_password" type="password" placeholder="留空则保留当前 SMTP 密码" />
            </label>

            <label>
              <span>发件人名称</span>
              <input v-model="aliyunDraft.from_name" type="text" placeholder="Enterprise AI QA Agent" />
            </label>

            <label class="full">
              <span>Reply-To</span>
              <input v-model="aliyunDraft.reply_to" type="email" placeholder="reply@example.com" />
            </label>

            <label class="checkbox-row">
              <input v-model="aliyunDraft.enabled" type="checkbox" />
              <span>启用该邮件提供商</span>
            </label>

            <label class="checkbox-row">
              <input v-model="aliyunDraft.is_default" type="checkbox" />
              <span>设为默认邮件通道</span>
            </label>
          </template>

          <template v-else>
            <label>
              <span>SMTP Host</span>
              <input v-model="cybermailDraft.smtp_host" type="text" placeholder="smtp.example.jp" />
            </label>

            <label>
              <span>SMTP 端口</span>
              <NSelect
                v-model:value="cybermailDraft.smtp_port"
                class="settings-provider-select"
                :options="CYBERMAIL_PORT_OPTIONS"
                :consistent-menu-width="false"
              />
            </label>

            <label>
              <span>SMTP 用户名</span>
              <input v-model="cybermailDraft.smtp_username" type="text" placeholder="mailer@example.com" />
            </label>

            <label>
              <span>SMTP 密码</span>
              <input v-model="cybermailDraft.smtp_password" type="password" placeholder="留空则保留当前 SMTP 密码" />
            </label>

            <label>
              <span>发信地址</span>
              <input v-model="cybermailDraft.from_email" type="email" placeholder="mailer@example.com" />
            </label>

            <label>
              <span>发件人名称</span>
              <input v-model="cybermailDraft.from_name" type="text" placeholder="Enterprise AI QA Agent" />
            </label>

            <label class="full">
              <span>Reply-To</span>
              <input v-model="cybermailDraft.reply_to" type="email" placeholder="reply@example.com" />
            </label>

            <label class="checkbox-row">
              <input v-model="cybermailDraft.enabled" type="checkbox" />
              <span>启用该邮件提供商</span>
            </label>

            <label class="checkbox-row">
              <input v-model="cybermailDraft.is_default" type="checkbox" />
              <span>设为默认邮件通道</span>
            </label>
          </template>
        </div>

        <div class="settings-actions">
          <button class="primary-btn narrow" :disabled="loading || saving" @click="saveEmail()">
            {{ saving ? "保存中..." : isCreateMode ? "保存新邮件通道" : "保存邮件配置" }}
          </button>
        </div>
      </section>
    </div>
  </section>
</template>
