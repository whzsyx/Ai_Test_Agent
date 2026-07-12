<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { NPopover, NSelect, type SelectOption } from "naive-ui";

import { api } from "../../../services/api";
import { t } from "../../../services/i18n";
import type {
  EmailConfigCreateRequest,
  EmailConfigPublic,
  EmailConfigUpdateRequest,
} from "../../../types";

type MessageTone = "success" | "error";
type DeliveryMode = "api" | "smtp";
type ChannelDirection = "delivery" | "agent_mailbox";
type EmailProvider =
  | "aliyun"
  | "tencent_ses"
  | "cybermail"
  | "sendgrid"
  | "mailgun"
  | "postmark"
  | "resend"
  | "brevo"
  | "mailchimp"
  | "zoho_campaigns"
  | "tencent_agently"
  | "agentmail"
  | "robotomail"
  | "openmail"
  | "dead_simple_email"
  | "agenticmail"
  | "aws_agent_mailbox";

interface ProviderGuide {
  title: string;
  summary: string;
  strengths: string[];
  requirements: string[];
  docs: Array<{ label: string; href: string }>;
}

interface ProviderProfile {
  value: EmailProvider;
  label: string;
  channelLabel: string;
  strengths: string;
  deliverability: string;
  freeTier: string;
  supportsApi: boolean;
  supportsSmtp: boolean;
  defaultMode: DeliveryMode;
  defaultName: string;
  defaultPort?: number | null;
  defaultHost?: string | null;
  guide: ProviderGuide;
}

interface EmailDraft {
  config_name: string;
  provider: EmailProvider;
  delivery_mode: DeliveryMode;
  api_key: string;
  secret_key: string;
  sender_email: string;
  test_email: string;
  test_mode: boolean;
  enabled: boolean;
  is_default: boolean;
  description: string;
  smtp_host: string;
  smtp_port: number | null;
  smtp_username: string;
  extra_config: Record<string, string>;
}

interface AgentMailboxProfile {
  authType: "api_key" | "cli_oauth" | "local_api" | "api_or_mcp";
  capabilities: string;
}

const DEFAULT_SMTP_PORT = 587;
const CYBERMAIL_HOST = "mail.cyberpersons.com";
const CYBERMAIL_PORT = 587;
const SENDGRID_SMTP_HOST = "smtp.sendgrid.net";
const SENDGRID_SMTP_PORT = 587;
const BREVO_SMTP_HOST = "smtp-relay.brevo.com";
const BREVO_SMTP_PORT = 587;
const ZOHO_SMTP_HOST = "smtp.zoho.com";
const ZOHO_SMTP_PORT = 587;
const TENCENT_SES_SMTP_HOST = "smtp.qcloudmail.com";
const TENCENT_SES_SMTP_PORT = 465;

const PROVIDER_PROFILES: ProviderProfile[] = [
  {
    value: "aliyun",
    label: "阿里云邮件推送",
    channelLabel: "DirectMail API / SMTP",
    strengths: "国内稳定，与阿里云生态集成好",
    deliverability: "高",
    freeTier: "需查询官网",
    supportsApi: true,
    supportsSmtp: true,
    defaultMode: "api",
    defaultName: "阿里云邮件推送",
    defaultPort: 465,
    defaultHost: "",
    guide: {
      title: "阿里云邮件推送",
      summary: "支持 DirectMail API 和 SMTP 两种接入方式，国内业务常用。",
      strengths: ["DirectMail API 适合系统事务邮件。", "SMTP 适合兼容历史系统或第三方网关。"],
      requirements: ["先完成发信域名和发信地址验证。", "API 模式需要 AccessKey ID / Secret。", "SMTP 模式需要发信地址和 SMTP 密码。"],
      docs: [{ label: "DirectMail API", href: "https://next.api.aliyun.com/document/Dm/2015-11-23/SingleSendMail" }, { label: "SMTP 发送邮件", href: "https://help.aliyun.com/zh/direct-mail/user-guide/send-emails-using-smtp" }],
    },
  },
  {
    value: "tencent_ses",
    label: "腾讯云 SES",
    channelLabel: "腾讯云 SES",
    strengths: "国内送达率高，与微信生态整合好",
    deliverability: "97% - 99%+",
    freeTier: "新用户 10 万封/月",
    supportsApi: true,
    supportsSmtp: true,
    defaultMode: "api",
    defaultName: "腾讯云 SES",
    defaultPort: TENCENT_SES_SMTP_PORT,
    defaultHost: TENCENT_SES_SMTP_HOST,
    guide: {
      title: "腾讯云 SES",
      summary: "支持 API 与 SMTP，适合金融、电商等国内高送达业务。",
      strengths: ["域名认证流程完善，适合大体量事务邮件。", "可选 SMTP 密码，兼容旧系统迁移。"],
      requirements: ["完成发信域名、SPF / DKIM / DMARC 配置。", "API 模式需要 SecretId / SecretKey。", "SMTP 模式需要发信地址、SMTP 用户名与密码。"],
      docs: [{ label: "腾讯云 SES", href: "https://www.tencentcloud.com/zh/document/product/1084" }],
    },
  },
  {
    value: "cybermail",
    label: "CyberMail SMTP",
    channelLabel: "CyberMail SMTP",
    strengths: "企业内网或日系环境常见，SMTP 接入清晰",
    deliverability: "高",
    freeTier: "无公开免费额度",
    supportsApi: false,
    supportsSmtp: true,
    defaultMode: "smtp",
    defaultName: "CyberMail SMTP",
    defaultPort: CYBERMAIL_PORT,
    defaultHost: CYBERMAIL_HOST,
    guide: {
      title: "CyberMail SMTP",
      summary: "使用固定 SMTP 主机与端口，适合企业事务邮件接入。",
      strengths: ["SMTP 迁移成本低。", "适合已有邮件管理员体系的企业。"],
      requirements: ["填写 SMTP 用户名和密码。", "发信邮箱需要与管理员分配身份一致。"],
      docs: [{ label: "CyberMail SMTP 说明", href: "https://cloud-sup.cybersolutions.co.jp/hc/ja/articles/360039314431" }],
    },
  },
  {
    value: "sendgrid",
    label: "SendGrid",
    channelLabel: "Twilio SendGrid",
    strengths: "国际主流，文档完善，并发能力强",
    deliverability: "95% - 96%",
    freeTier: "100 封/天",
    supportsApi: true,
    supportsSmtp: true,
    defaultMode: "api",
    defaultName: "SendGrid",
    defaultPort: SENDGRID_SMTP_PORT,
    defaultHost: SENDGRID_SMTP_HOST,
    guide: {
      title: "SendGrid",
      summary: "支持 Web API 和 SMTP Relay，适合国际业务。",
      strengths: ["文档完善，生态成熟。", "高并发事务邮件支持好。"],
      requirements: ["API 模式需要 API Key。", "SMTP 模式通常使用用户名 apikey 和 API Key 作为密码。"],
      docs: [{ label: "API Keys", href: "https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys" }, { label: "SMTP Relay", href: "https://www.twilio.com/docs/sendgrid/for-developers/sending-email/integrating-with-the-smtp-api" }],
    },
  },
  {
    value: "mailgun",
    label: "Mailgun",
    channelLabel: "Mailgun API",
    strengths: "开发者友好，事务性邮件能力强",
    deliverability: "高",
    freeTier: "100 封/天",
    supportsApi: true,
    supportsSmtp: false,
    defaultMode: "api",
    defaultName: "Mailgun",
    guide: {
      title: "Mailgun",
      summary: "常见于事务性通知和事件触发邮件场景。",
      strengths: ["API 简洁，域名管理清晰。", "Webhook 与事件追踪能力较强。"],
      requirements: ["需要 API Key。", "通常还需要发信域名。"],
      docs: [{ label: "Mailgun API", href: "https://documentation.mailgun.com/docs/mailgun/api-reference/send/mailgun/messages/post-v3--domain-name--messages" }],
    },
  },
  {
    value: "postmark",
    label: "Postmark",
    channelLabel: "Postmark API",
    strengths: "专注事务性邮件，速度快",
    deliverability: "高",
    freeTier: "100 封/月",
    supportsApi: true,
    supportsSmtp: false,
    defaultMode: "api",
    defaultName: "Postmark",
    guide: {
      title: "Postmark",
      summary: "偏事务邮件，强调送达速度和开发者体验。",
      strengths: ["Server Token 模式清晰。", "模板和 webhook 体验稳定。"],
      requirements: ["需要 Server API Token。"],
      docs: [{ label: "Postmark API", href: "https://postmarkapp.com/developer/user-guide/send-email-with-api" }],
    },
  },
  {
    value: "resend",
    label: "Resend",
    channelLabel: "Resend API",
    strengths: "现代化，开发者体验优秀",
    deliverability: "高",
    freeTier: "3000 封/月",
    supportsApi: true,
    supportsSmtp: false,
    defaultMode: "api",
    defaultName: "Resend",
    guide: {
      title: "Resend",
      summary: "新兴热门邮件服务，API 体验很好。",
      strengths: ["上手快，前后端一体化体验好。", "事务邮件与 React 邮件生态友好。"],
      requirements: ["需要 API Key。", "建议先完成发信域名验证。"],
      docs: [{ label: "Resend API Keys", href: "https://resend.com/docs/dashboard/api-keys/introduction" }, { label: "Resend Domains", href: "https://resend.com/docs/dashboard/domains/introduction" }],
    },
  },
  {
    value: "brevo",
    label: "Brevo",
    channelLabel: "Brevo API / SMTP",
    strengths: "功能全面，集成 CRM 和自动化",
    deliverability: "92% - 94%",
    freeTier: "300 封/天",
    supportsApi: true,
    supportsSmtp: true,
    defaultMode: "api",
    defaultName: "Brevo",
    defaultPort: BREVO_SMTP_PORT,
    defaultHost: BREVO_SMTP_HOST,
    guide: {
      title: "Brevo",
      summary: "原 Sendinblue，营销与事务邮件都可用。",
      strengths: ["支持 API 和 SMTP。", "CRM 和自动化能力一体化。"],
      requirements: ["API 模式需要 API Key。", "SMTP 模式需要 SMTP 用户名与密码。"],
      docs: [{ label: "Brevo API Key", href: "https://developers.brevo.com/docs/getting-started" }, { label: "Brevo SMTP", href: "https://help.brevo.com/hc/en-us/articles/209467485-What-are-the-Brevo-SMTP-server-parameters" }],
    },
  },
  {
    value: "mailchimp",
    label: "Mailchimp",
    channelLabel: "Mailchimp API",
    strengths: "营销能力强，可视化编辑成熟",
    deliverability: "90% - 95%",
    freeTier: "免费版功能受限",
    supportsApi: true,
    supportsSmtp: false,
    defaultMode: "api",
    defaultName: "Mailchimp",
    guide: {
      title: "Mailchimp",
      summary: "适合营销邮件和中小企业运营场景。",
      strengths: ["营销自动化和模板能力强。", "适合内容运营团队。"],
      requirements: ["需要 API Key。"],
      docs: [{ label: "Mailchimp API Keys", href: "https://mailchimp.com/developer/marketing/docs/fundamentals/?form=MG0AV3" }],
    },
  },
  {
    value: "zoho_campaigns",
    label: "Zoho Campaigns",
    channelLabel: "Zoho Campaigns",
    strengths: "多语言支持和合规能力较好",
    deliverability: "95%+",
    freeTier: "付费版 $28 起/用户",
    supportsApi: true,
    supportsSmtp: true,
    defaultMode: "api",
    defaultName: "Zoho Campaigns",
    defaultPort: ZOHO_SMTP_PORT,
    defaultHost: ZOHO_SMTP_HOST,
    guide: {
      title: "Zoho Campaigns",
      summary: "适合跨国企业营销和事务邮件混合场景。",
      strengths: ["支持多语言和 GDPR 合规。", "可根据场景切 API 或 SMTP。"],
      requirements: ["API 模式需要 API Key 或 OAuth 凭证。", "SMTP 模式需要 SMTP 主机、端口、用户名与密码。"],
      docs: [{ label: "Zoho Campaigns API", href: "https://www.zoho.com/campaigns/help/developers/get-started-api.html" }],
    },
  },
];

const AGENT_MAILBOX_PROFILES: ProviderProfile[] = [
  {
    value: "tencent_agently", label: "Tencent Agent Mail", channelLabel: "CLI + OAuth",
    strengths: "通过 agently-cli 提供完整信箱收发与管理能力", deliverability: "由信箱服务决定", freeTier: "按服务商规则",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "Tencent Agent Mail",
    guide: { title: "Tencent Agent Mail", summary: "使用 agently-cli 与 OAuth 接入 Agent 信箱。", strengths: ["支持发送、接收、搜索、回复、转发和附件。"], requirements: ["本机需要安装并登录 agently-cli。"], docs: [] },
  },
  {
    value: "agentmail", label: "AgentMail", channelLabel: "REST API",
    strengths: "支持信箱创建、Webhook 与完整邮件操作", deliverability: "由信箱服务决定", freeTier: "按服务商规则",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "AgentMail",
    guide: { title: "AgentMail", summary: "通过 REST API 接入 AgentMail 信箱。", strengths: ["支持 provision inbox、Webhook 和完整邮件操作。"], requirements: ["需要 API Key，可选自定义 Base URL。"], docs: [] },
  },
  {
    value: "robotomail", label: "Robotomail", channelLabel: "REST API",
    strengths: "支持信箱管理、Webhook 与完整邮件操作", deliverability: "由信箱服务决定", freeTier: "按服务商规则",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "Robotomail",
    guide: { title: "Robotomail", summary: "通过 REST API 接入 Robotomail。", strengths: ["支持信箱管理、Webhook 和完整邮件操作。"], requirements: ["需要 API Key，可选自定义 Base URL。"], docs: [] },
  },
  {
    value: "openmail", label: "OpenMail", channelLabel: "REST API / WebSocket",
    strengths: "支持实时 WebSocket 消息能力", deliverability: "由信箱服务决定", freeTier: "按服务商规则",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "OpenMail",
    guide: { title: "OpenMail", summary: "通过 REST API 和 WebSocket 接入 OpenMail。", strengths: ["适合需要实时邮件事件的 Agent。"], requirements: ["需要 API Key，可选自定义 Base URL。"], docs: [] },
  },
  {
    value: "dead_simple_email", label: "Dead Simple Email", channelLabel: "REST API / IMAP / SMTP",
    strengths: "REST API 结合 IMAP/SMTP 兼容能力", deliverability: "由信箱服务决定", freeTier: "按服务商规则",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "Dead Simple Email",
    guide: { title: "Dead Simple Email", summary: "通过 REST API 接入，支持 IMAP/SMTP fallback。", strengths: ["对传统邮件协议兼容较好。"], requirements: ["需要 API Key，可选自定义 Base URL。"], docs: [] },
  },
  {
    value: "agenticmail", label: "AgenticMail", channelLabel: "Local API / MCP / SSE",
    strengths: "适合自托管的本地 Agent 邮箱服务", deliverability: "由本地服务决定", freeTier: "自托管",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "AgenticMail",
    guide: { title: "AgenticMail", summary: "通过本地 API、MCP 与 SSE 接入自托管信箱。", strengths: ["数据和运行环境可由企业自行控制。"], requirements: ["需要填写本地服务 Base URL。"], docs: [] },
  },
  {
    value: "aws_agent_mailbox", label: "AWS Agent Mailbox", channelLabel: "HTTP API / MCP",
    strengths: "基于 AWS 的 API 或 MCP 信箱接入", deliverability: "由 AWS 服务决定", freeTier: "按 AWS 规则",
    supportsApi: true, supportsSmtp: false, defaultMode: "api", defaultName: "AWS Agent Mailbox",
    guide: { title: "AWS Agent Mailbox", summary: "通过 HTTP API 或 MCP 配置接入 AWS Agent Mailbox。", strengths: ["适合已经使用 AWS 基础设施的团队。"], requirements: ["填写 API Key 或对应 MCP/API 配置。"], docs: [] },
  },
];

const ALL_PROVIDER_PROFILES = [...PROVIDER_PROFILES, ...AGENT_MAILBOX_PROFILES];
const AGENT_MAILBOX_PROVIDER_KEYS = new Set<EmailProvider>(
  AGENT_MAILBOX_PROFILES.map((profile) => profile.value),
);
const AGENT_MAILBOX_AUTH: Record<string, AgentMailboxProfile> = {
  tencent_agently: { authType: "cli_oauth", capabilities: "发送、接收、搜索、回复、转发、附件" },
  agentmail: { authType: "api_key", capabilities: "信箱创建、发送、接收、Webhook" },
  robotomail: { authType: "api_key", capabilities: "信箱管理、发送、接收、Webhook" },
  openmail: { authType: "api_key", capabilities: "发送、接收、WebSocket" },
  dead_simple_email: { authType: "api_key", capabilities: "发送、接收、IMAP/SMTP fallback" },
  agenticmail: { authType: "local_api", capabilities: "本地 API、MCP、SSE" },
  aws_agent_mailbox: { authType: "api_or_mcp", capabilities: "HTTP API、MCP" },
};

const PROVIDER_BY_KEY = Object.fromEntries(
  ALL_PROVIDER_PROFILES.map((profile) => [profile.value, profile]),
) as Record<EmailProvider, ProviderProfile>;

const CHANNEL_DIRECTION_OPTIONS: SelectOption[] = [
  { label: "邮件发送服务", value: "delivery" },
  { label: "Agent 邮箱", value: "agent_mailbox" },
];

const API_SMTP_MODE_OPTIONS: SelectOption[] = [
  { label: "API", value: "api" },
  { label: "SMTP", value: "smtp" },
];

const loading = ref(false);
const saving = ref(false);
const showEditorModal = ref(false);
const isCreateMode = ref(false);
const editingConfigId = ref<number | null>(null);
const busyActionKey = ref("");
const emailConfigs = ref<EmailConfigPublic[]>([]);
const messageVisible = ref(false);
const messageText = ref("");
const messageTone = ref<MessageTone>("success");
const channelDirection = ref<ChannelDirection>("delivery");
let messageTimer: ReturnType<typeof setTimeout> | null = null;

const draft = reactive<EmailDraft>(buildEmptyDraft("aliyun"));

const activeProfile = computed(() => PROVIDER_BY_KEY[draft.provider]);
const isAgentMailbox = computed(() => AGENT_MAILBOX_PROVIDER_KEYS.has(draft.provider));
const activeMailboxProfile = computed(() => AGENT_MAILBOX_AUTH[draft.provider]);
const providerOptions = computed<SelectOption[]>(() =>
  ALL_PROVIDER_PROFILES
    .filter((profile) => AGENT_MAILBOX_PROVIDER_KEYS.has(profile.value) === (channelDirection.value === "agent_mailbox"))
    .map((profile) => ({ label: profile.label, value: profile.value })),
);
const providerSupportsModeSwitch = computed(
  () => activeProfile.value.supportsApi && activeProfile.value.supportsSmtp,
);
const providerGuide = computed(() => activeProfile.value.guide);

onMounted(() => {
  void loadSettings();
});

onBeforeUnmount(() => {
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
});

function buildEmptyDraft(provider: EmailProvider): EmailDraft {
  const profile = PROVIDER_BY_KEY[provider];
  return {
    config_name: profile.defaultName,
    provider,
    delivery_mode: profile.defaultMode,
    api_key: "",
    secret_key: "",
    sender_email: "",
    test_email: "",
    test_mode: false,
    enabled: false,
    is_default: false,
    description: "",
    smtp_host: profile.defaultHost ?? "",
    smtp_port: profile.defaultPort ?? DEFAULT_SMTP_PORT,
    smtp_username: "",
    extra_config: {
      sending_domain: "",
      sender_name: "",
      api_token_label: "",
      base_url: "",
      cli_path: provider === "tencent_agently" ? "agently-cli" : "",
    },
  };
}

function applyDraft(nextDraft: EmailDraft) {
  draft.config_name = nextDraft.config_name;
  draft.provider = nextDraft.provider;
  draft.delivery_mode = nextDraft.delivery_mode;
  draft.api_key = nextDraft.api_key;
  draft.secret_key = nextDraft.secret_key;
  draft.sender_email = nextDraft.sender_email;
  draft.test_email = nextDraft.test_email;
  draft.test_mode = nextDraft.test_mode;
  draft.enabled = nextDraft.enabled;
  draft.is_default = nextDraft.is_default;
  draft.description = nextDraft.description;
  draft.smtp_host = nextDraft.smtp_host;
  draft.smtp_port = nextDraft.smtp_port;
  draft.smtp_username = nextDraft.smtp_username;
  draft.extra_config = { ...nextDraft.extra_config };
}

async function loadSettings() {
  loading.value = true;
  try {
    emailConfigs.value = await api.listEmailConfigs();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : t("emailSettings.load_failed"));
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

function getProviderLabel(provider: string) {
  return PROVIDER_BY_KEY[provider as EmailProvider]?.label ?? provider;
}

function getDeliveryMode(item: EmailConfigPublic): DeliveryMode {
  const value = item.extra_config?.delivery_mode;
  return value === "smtp" ? "smtp" : "api";
}

function describeChannel(item: EmailConfigPublic) {
  if (AGENT_MAILBOX_PROVIDER_KEYS.has(item.provider as EmailProvider)) {
    return `Agent 邮箱 · ${PROVIDER_BY_KEY[item.provider as EmailProvider]?.channelLabel || "API"}`;
  }
  const mode = getDeliveryMode(item);
  if (mode === "smtp") {
    const host = item.smtp_host || "N/A";
    const port = item.smtp_port ? `:${item.smtp_port}` : "";
    return `${host}${port}`;
  }
  const provider = item.provider as EmailProvider;
  if (provider === "aliyun") {
    return "DirectMail API";
  }
  if (provider === "tencent_ses") {
    return "SES API";
  }
  return "API";
}

function describeAuth(item: EmailConfigPublic) {
  const mode = getDeliveryMode(item);
  const provider = item.provider as EmailProvider;
  if (AGENT_MAILBOX_PROVIDER_KEYS.has(provider)) {
    const authType = AGENT_MAILBOX_AUTH[provider]?.authType;
    if (authType === "cli_oauth") return "CLI / OAuth";
    if (authType === "local_api") return "本地 API";
    return item.has_api_key ? t("emailSettings.apikey_configured") : t("emailSettings.apikey_not_configured");
  }
  if (mode === "smtp") {
    return item.has_api_key ? t("emailSettings.smtp_auth_configured") : t("emailSettings.smtp_auth_not_configured");
  }
  if (provider === "aliyun") {
    return item.has_api_key && item.has_secret_key ? t("emailSettings.accesskey_configured") : t("emailSettings.accesskey_not_configured");
  }
  if (provider === "tencent_ses") {
    return item.has_api_key && item.has_secret_key ? t("emailSettings.secretid_configured") : t("emailSettings.secretid_not_configured");
  }
  return item.has_api_key ? t("emailSettings.apikey_configured") : t("emailSettings.apikey_not_configured");
}

function describeSenderName(item: EmailConfigPublic) {
  return String(item.extra_config?.sender_name || "").trim() || t("emailSettings.not_set");
}

function actionKey(configId: number, action: string) {
  return `${configId}:${action}`;
}

function openCreateModal() {
  isCreateMode.value = true;
  editingConfigId.value = null;
  applyDraft(buildEmptyDraft("aliyun"));
  channelDirection.value = "delivery";
  showEditorModal.value = true;
}

function openEditModal(item: EmailConfigPublic) {
  const provider = item.provider as EmailProvider;
  const profile = PROVIDER_BY_KEY[provider] ?? PROVIDER_BY_KEY.aliyun;
  const mode = getDeliveryMode(item);
  isCreateMode.value = false;
  channelDirection.value = AGENT_MAILBOX_PROVIDER_KEYS.has(provider) ? "agent_mailbox" : "delivery";
  editingConfigId.value = item.id;
  applyDraft({
    config_name: item.config_name,
    provider,
    delivery_mode: profile.supportsSmtp && !profile.supportsApi ? "smtp" : mode,
    api_key: "",
    secret_key: "",
    sender_email: item.sender_email || "",
    test_email: item.test_email || "",
    test_mode: item.test_mode,
    enabled: item.enabled,
    is_default: item.is_default,
    description: item.description || "",
    smtp_host: item.smtp_host || profile.defaultHost || "",
    smtp_port: item.smtp_port || profile.defaultPort || DEFAULT_SMTP_PORT,
    smtp_username: item.smtp_username || "",
    extra_config: {
      sending_domain: String(item.extra_config?.sending_domain || ""),
      sender_name: String(item.extra_config?.sender_name || ""),
      api_token_label: String(item.extra_config?.api_token_label || ""),
      base_url: String(item.extra_config?.base_url || ""),
      cli_path: String(item.extra_config?.cli_path || (provider === "tencent_agently" ? "agently-cli" : "")),
    },
  });
  showEditorModal.value = true;
}

function closeEditorModal() {
  showEditorModal.value = false;
  editingConfigId.value = null;
}

function syncModeDefaults(provider: EmailProvider, mode: DeliveryMode) {
  const profile = PROVIDER_BY_KEY[provider];
  if (mode === "smtp") {
    draft.smtp_host = profile.defaultHost ?? draft.smtp_host ?? "";
    draft.smtp_port = profile.defaultPort ?? draft.smtp_port ?? DEFAULT_SMTP_PORT;
    if (provider === "sendgrid" && !draft.smtp_username.trim()) {
      draft.smtp_username = "apikey";
    }
  } else if (!profile.supportsSmtp) {
    draft.smtp_host = profile.defaultHost ?? "";
    draft.smtp_port = profile.defaultPort ?? DEFAULT_SMTP_PORT;
    draft.smtp_username = "";
  }
}

function handleProviderChange(value: string) {
  const provider = value as EmailProvider;
  if (!PROVIDER_BY_KEY[provider] || provider === draft.provider) {
    return;
  }
  const nextDraft = buildEmptyDraft(provider);
  nextDraft.config_name = draft.config_name.trim() ? draft.config_name : nextDraft.config_name;
  nextDraft.enabled = draft.enabled;
  nextDraft.is_default = draft.is_default;
  nextDraft.test_mode = draft.test_mode;
  nextDraft.test_email = draft.test_email;
  nextDraft.description = draft.description;
  applyDraft(nextDraft);
}

function handleDirectionChange(value: string) {
  const direction = value as ChannelDirection;
  if (direction === channelDirection.value) return;
  channelDirection.value = direction;
  const provider: EmailProvider = direction === "agent_mailbox" ? "agentmail" : "aliyun";
  const nextDraft = buildEmptyDraft(provider);
  nextDraft.enabled = draft.enabled;
  nextDraft.is_default = draft.is_default;
  nextDraft.test_mode = draft.test_mode;
  applyDraft(nextDraft);
}

function handleModeChange(value: string) {
  const mode = value as DeliveryMode;
  draft.delivery_mode = mode;
  syncModeDefaults(draft.provider, mode);
}

function buildExtraConfig() {
  const extra: Record<string, unknown> = {
    delivery_mode: draft.delivery_mode,
    channel_direction: channelDirection.value,
  };
  if (draft.extra_config.sending_domain?.trim()) {
    extra.sending_domain = draft.extra_config.sending_domain.trim();
  }
  if (draft.extra_config.sender_name?.trim()) {
    extra.sender_name = draft.extra_config.sender_name.trim();
  }
  if (draft.extra_config.api_token_label?.trim()) {
    extra.api_token_label = draft.extra_config.api_token_label.trim();
  }
  if (draft.extra_config.base_url?.trim()) extra.base_url = draft.extra_config.base_url.trim();
  if (draft.extra_config.cli_path?.trim()) extra.cli_path = draft.extra_config.cli_path.trim();
  return extra;
}

function buildCreatePayload(): EmailConfigCreateRequest {
  const smtpEnabled = draft.delivery_mode === "smtp";
  return {
    config_name: draft.config_name.trim(),
    provider: draft.provider,
    enabled: draft.enabled || draft.is_default,
    is_default: draft.is_default,
    api_key: draft.api_key.trim() || null,
    secret_key: draft.secret_key.trim() || null,
    sender_email: draft.sender_email.trim(),
    test_email: draft.test_email.trim() || null,
    test_mode: draft.test_mode,
    description: draft.description.trim() || null,
    smtp_host: smtpEnabled ? draft.smtp_host.trim() || null : null,
    smtp_port: smtpEnabled ? Number(draft.smtp_port || DEFAULT_SMTP_PORT) : null,
    smtp_username: smtpEnabled ? draft.smtp_username.trim() || null : null,
    extra_config: buildExtraConfig(),
  };
}

function buildUpdatePayload(): EmailConfigUpdateRequest {
  return buildCreatePayload();
}

function validateDraft() {
  if (!draft.config_name.trim()) {
    showMessage("error", t("emailSettings.v_channel_name"));
    return false;
  }
  if (!isAgentMailbox.value && !draft.sender_email.trim()) {
    showMessage("error", t("emailSettings.v_sender_email"));
    return false;
  }
  if (draft.delivery_mode === "api") {
    const mailboxAuth = activeMailboxProfile.value?.authType;
    const requiresApiKey = !isAgentMailbox.value || mailboxAuth === "api_key" || mailboxAuth === "api_or_mcp";
    if (requiresApiKey && !draft.api_key.trim() && isCreateMode.value) {
      showMessage("error", t("emailSettings.v_api_key"));
      return false;
    }
    if ((draft.provider === "aliyun" || draft.provider === "tencent_ses") && !draft.secret_key.trim() && isCreateMode.value) {
      showMessage("error", t("emailSettings.v_secret_key"));
      return false;
    }
    if (draft.provider === "mailgun" && !draft.extra_config.sending_domain?.trim()) {
      showMessage("error", t("emailSettings.v_mailgun_domain"));
      return false;
    }
    if (draft.provider === "resend" && !draft.extra_config.sending_domain?.trim()) {
      showMessage("error", t("emailSettings.v_resend_domain"));
      return false;
    }
    if (mailboxAuth === "local_api" && !draft.extra_config.base_url?.trim()) {
      showMessage("error", "请填写 Agent 邮箱服务 Base URL。");
      return false;
    }
  } else {
    if (!draft.smtp_host.trim()) {
      showMessage("error", t("emailSettings.v_smtp_host"));
      return false;
    }
    if (!draft.smtp_port) {
      showMessage("error", t("emailSettings.v_smtp_port"));
      return false;
    }
    if (!draft.smtp_username.trim()) {
      showMessage("error", t("emailSettings.v_smtp_username"));
      return false;
    }
    if (!draft.api_key.trim() && isCreateMode.value) {
      showMessage("error", t("emailSettings.v_smtp_password"));
      return false;
    }
  }
  return true;
}

async function saveEmail() {
  if (!validateDraft()) {
    return;
  }
  saving.value = true;
  try {
    if (isCreateMode.value) {
      const created = await api.createEmailConfig(buildCreatePayload());
      showMessage("success", `${t("emailSettings.channel_created")}: ${created.config_name}`);
    } else if (editingConfigId.value !== null) {
      const updated = await api.updateEmailConfig(editingConfigId.value, buildUpdatePayload());
      showMessage("success", `${t("emailSettings.channel_updated")}: ${updated.config_name}`);
    }
    closeEditorModal();
    await loadSettings();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : t("emailSettings.save_failed"));
  } finally {
    saving.value = false;
  }
}

async function withAction(configId: number, action: string, runner: () => Promise<void>) {
  busyActionKey.value = actionKey(configId, action);
  try {
    await runner();
  } catch (err) {
    showMessage("error", err instanceof Error ? err.message : t("emailSettings.action_failed"));
  } finally {
    busyActionKey.value = "";
  }
}

async function testConnection(item: EmailConfigPublic) {
  await withAction(item.id, "test", async () => {
    if (AGENT_MAILBOX_PROVIDER_KEYS.has(item.provider as EmailProvider)) {
      const result = await api.mailProviderStatus(item.provider);
      const ok = result.ok === true;
      const detail = String(result.error || result.message || (ok ? "Agent 邮箱连接正常。" : "Agent 邮箱连接失败。"));
      showMessage(ok ? "success" : "error", detail);
      return;
    }
    const result = await api.testEmailConfigConnection(item.id);
    showMessage(result.ok ? "success" : "error", result.preview ? `${result.message} ${result.preview}` : result.message);
  });
}

async function activateChannel(item: EmailConfigPublic) {
  await withAction(item.id, "activate", async () => {
    const result = await api.activateEmailConfig(item.id);
    showMessage("success", result.message);
    await loadSettings();
  });
}

async function deleteChannel(item: EmailConfigPublic) {
  const confirmed = window.confirm(`${t("emailSettings.confirm_delete")} "${item.config_name}"?`);
  if (!confirmed) {
    return;
  }
  await withAction(item.id, "delete", async () => {
    const result = await api.deleteEmailConfig(item.id);
    showMessage("success", result.message);
    await loadSettings();
  });
}

function requiresSendingDomain(provider: EmailProvider) {
  return ["tencent_ses", "mailgun", "resend", "aliyun"].includes(provider);
}

function apiKeyLabel(provider: EmailProvider) {
  switch (provider) {
    case "aliyun":
      return "Access Key ID";
    case "tencent_ses":
      return "SecretId";
    case "postmark":
      return "Server API Token";
    default:
      return "API Key";
  }
}

function secretKeyLabel(provider: EmailProvider) {
  return provider === "aliyun" ? "Access Key Secret" : "SecretKey";
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
        <h3>{{ t("emailSettings.title") }}</h3>
        <p>{{ t("emailSettings.desc") }}</p>
      </div>
    </div>

    <div class="settings-pane-block settings-model-grid-shell">
      <div class="settings-model-grid settings-email-grid">
        <article
          v-for="item in emailConfigs"
          :key="item.id"
          class="settings-model-card settings-model-card-static settings-email-card"
        >
          <div class="settings-model-card__header">
            <span class="settings-model-card__badge" :class="item.enabled ? 'settings-model-card__badge-current' : ''">
              {{ item.enabled ? t("emailSettings.enabled") : t("emailSettings.disabled") }}
            </span>
            <span v-if="item.is_default" class="settings-model-card__badge settings-model-card__badge-current">
              {{ t("emailSettings.default_channel") }}
            </span>
          </div>

          <div class="settings-model-card__name">
            <strong>{{ item.config_name }}</strong>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-layer-group"></i>
            <span>{{ getProviderLabel(item.provider) }}</span>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-envelope"></i>
            <span>{{ item.sender_email || t("emailSettings.no_sender_email") }}</span>
          </div>

          <div class="settings-model-card__provider-row">
            <i class="fa-solid fa-server"></i>
            <span>{{ describeChannel(item) }}</span>
          </div>

          <div class="settings-model-card__stat">
            <span>{{ t("emailSettings.auth_status") }}</span>
            <strong>{{ describeAuth(item) }}</strong>
          </div>

          <div class="settings-model-card__stat">
            <span>{{ t("emailSettings.sender_name") }}</span>
            <strong>{{ describeSenderName(item) }}</strong>
          </div>

          <div class="settings-model-card__actions settings-email-card__actions">
            <NPopover trigger="hover" placement="top" :show-arrow="false">
              <template #trigger>
                <button class="settings-model-card__action" type="button" :aria-label="t('emailSettings.config_guide')">
                  <i class="fa-solid fa-circle-info"></i>
                </button>
              </template>
              <div class="settings-email-popover settings-email-popover-wide">
                <strong>{{ PROVIDER_BY_KEY[item.provider as EmailProvider]?.guide.title || getProviderLabel(item.provider) }}</strong>
                <p>{{ PROVIDER_BY_KEY[item.provider as EmailProvider]?.guide.summary }}</p>
                <ul>
                  <li
                    v-for="requirement in PROVIDER_BY_KEY[item.provider as EmailProvider]?.guide.requirements || []"
                    :key="requirement"
                  >
                    {{ requirement }}
                  </li>
                </ul>
              </div>
            </NPopover>

            <button
              class="settings-model-card__action settings-model-card__action-test"
              type="button"
              :disabled="busyActionKey === actionKey(item.id, 'test')"
              @click="testConnection(item)"
            >
              <i class="fa-solid fa-plug-circle-check"></i>
            </button>

            <button
              class="settings-model-card__action settings-model-card__action-activate"
              type="button"
              :disabled="item.is_default || busyActionKey === actionKey(item.id, 'activate')"
              @click="activateChannel(item)"
            >
              <i class="fa-solid fa-circle-check"></i>
            </button>

            <button
              class="settings-model-card__action settings-model-card__action-edit"
              type="button"
              @click="openEditModal(item)"
            >
              <i class="fa-solid fa-pen-to-square"></i>
            </button>

            <button
              class="settings-model-card__action settings-model-card__action-danger"
              type="button"
              :disabled="busyActionKey === actionKey(item.id, 'delete')"
              @click="deleteChannel(item)"
            >
              <i class="fa-solid fa-trash"></i>
            </button>
          </div>
        </article>

        <button
          class="settings-model-card settings-model-card-add settings-email-card settings-email-card-add"
          type="button"
          @click="openCreateModal"
        >
          <span class="settings-model-card-add__icon">+</span>
          <div class="settings-model-card-add__body">
            <strong>{{ t("emailSettings.add_channel") }}</strong>
            <p>{{ t("emailSettings.add_card_desc") }}</p>
          </div>
        </button>
      </div>
    </div>

    <div v-if="showEditorModal" class="settings-modal-overlay" @click.self="closeEditorModal">
      <div class="settings-modal-card settings-modal-card-clean">
        <div class="settings-modal-head">
          <div>
            <h4>{{ isCreateMode ? t("emailSettings.add_channel") : t("emailSettings.edit_channel") }}</h4>
            <p>
              {{ isCreateMode ? t("emailSettings.add_channel_desc") : t("emailSettings.edit_channel_desc") }}
            </p>
          </div>
          <button class="settings-modal-close" type="button" @click="closeEditorModal">
            ×
          </button>
        </div>

        <div class="settings-email-modal-tip">
          <NPopover trigger="hover" placement="bottom-end" :show-arrow="false">
            <template #trigger>
              <button class="settings-email-tip-btn" type="button">
                <i class="fa-solid fa-circle-info"></i>
                <span>{{ t("emailSettings.config_guide") }}</span>
              </button>
            </template>
            <div class="settings-email-popover settings-email-popover-wide">
              <strong>{{ providerGuide.title }}</strong>
              <p>{{ providerGuide.summary }}</p>
              <ul>
                <li v-for="item in providerGuide.strengths" :key="item">{{ item }}</li>
              </ul>
              <div class="settings-email-docs">
                <a
                  v-for="doc in providerGuide.docs"
                  :key="doc.href"
                  :href="doc.href"
                  target="_blank"
                  rel="noreferrer"
                >
                  {{ doc.label }}
                </a>
              </div>
            </div>
          </NPopover>
        </div>

        <div class="form-grid two">
          <label v-if="isCreateMode" class="full settings-provider-field">
            <span>通道方向</span>
            <NSelect
              :value="channelDirection"
              class="settings-provider-select"
              menu-class="settings-provider-select-menu"
              :options="CHANNEL_DIRECTION_OPTIONS"
              @update:value="(value) => handleDirectionChange(String(value))"
            />
          </label>

          <label class="full">
            <span>{{ t("emailSettings.channel_name") }}</span>
            <input v-model="draft.config_name" type="text" :placeholder="t('emailSettings.channel_name_ph')" />
          </label>

          <label class="settings-provider-field">
            <span>{{ t("emailSettings.provider") }}</span>
            <NSelect
              :value="draft.provider"
              class="settings-provider-select"
              menu-class="settings-provider-select-menu"
              :options="providerOptions"
              filterable
              consistent-menu-width
              :placeholder="t('emailSettings.provider_ph')"
              @update:value="(value) => handleProviderChange(String(value))"
            />
          </label>

          <label v-if="providerSupportsModeSwitch && !isAgentMailbox" class="settings-provider-field">
            <span>{{ t("emailSettings.delivery_mode") }}</span>
            <NSelect
              :value="draft.delivery_mode"
              class="settings-provider-select"
              menu-class="settings-provider-select-menu"
              :options="API_SMTP_MODE_OPTIONS"
              :placeholder="t('emailSettings.delivery_mode_ph')"
              @update:value="(value) => handleModeChange(String(value))"
            />
          </label>

          <label :class="providerSupportsModeSwitch ? '' : 'full'" v-if="requiresSendingDomain(draft.provider)">
            <span>{{ t("emailSettings.sending_domain") }}</span>
            <input
              v-model="draft.extra_config.sending_domain"
              type="text"
              :placeholder="t('emailSettings.sending_domain_ph')"
            />
          </label>

          <template v-if="draft.delivery_mode === 'api'">
            <label v-if="activeMailboxProfile?.authType !== 'cli_oauth' && activeMailboxProfile?.authType !== 'local_api'">
              <span>{{ apiKeyLabel(draft.provider) }}</span>
              <input
                v-model="draft.api_key"
                type="password"
                :placeholder="isCreateMode ? apiKeyLabel(draft.provider) : t('emailSettings.keep_current_hint')"
              />
            </label>

            <label v-if="activeMailboxProfile?.authType === 'cli_oauth'">
              <span>CLI Path</span>
              <input v-model="draft.extra_config.cli_path" type="text" placeholder="留空则自动从 PATH 发现 agently-cli" />
            </label>

            <label v-if="isAgentMailbox && activeMailboxProfile?.authType !== 'cli_oauth'">
              <span>Base URL{{ activeMailboxProfile?.authType === 'local_api' ? '' : '（可选）' }}</span>
              <input v-model="draft.extra_config.base_url" type="text" placeholder="https://api.example.com" />
            </label>

            <label v-if="isAgentMailbox" class="full">
              <span>信箱能力</span>
              <input :value="activeMailboxProfile?.capabilities" type="text" disabled />
            </label>

            <label v-if="draft.provider === 'aliyun' || draft.provider === 'tencent_ses'">
              <span>{{ secretKeyLabel(draft.provider) }}</span>
              <input
                v-model="draft.secret_key"
                type="password"
                :placeholder="isCreateMode ? secretKeyLabel(draft.provider) : t('emailSettings.keep_current_hint')"
              />
            </label>
          </template>

          <template v-else>
            <label>
              <span>SMTP Host</span>
              <input v-model="draft.smtp_host" type="text" placeholder="smtp.example.com" />
            </label>

            <label>
              <span>SMTP Port</span>
              <input v-model.number="draft.smtp_port" type="number" min="1" max="65535" placeholder="587" />
            </label>

            <label>
              <span>SMTP Username</span>
              <input v-model="draft.smtp_username" type="text" placeholder="SMTP Username" />
            </label>

            <label>
              <span>SMTP Password</span>
              <input
                v-model="draft.api_key"
                type="password"
                :placeholder="isCreateMode ? 'SMTP Password' : 'Leave empty to keep current SMTP password'"
              />
            </label>
          </template>

          <label>
            <span>{{ t("emailSettings.sender_email") }}</span>
            <input v-model="draft.sender_email" type="email" :placeholder="isAgentMailbox ? '可留空，按 Provider 创建或读取信箱' : 'notice@example.com'" />
          </label>

          <label>
            <span>{{ t("emailSettings.test_email") }}</span>
            <input v-model="draft.test_email" type="email" placeholder="test@example.com" />
          </label>

          <label>
            <span>{{ t("emailSettings.sender_name") }}</span>
            <input v-model="draft.extra_config.sender_name" type="text" :placeholder="t('emailSettings.sender_name_ph')" />
          </label>

          <label class="full">
            <span>{{ t("emailSettings.description") }}</span>
            <textarea v-model="draft.description" :placeholder="t('emailSettings.description_ph')"></textarea>
          </label>

          <label class="checkbox-row">
            <input v-model="draft.test_mode" type="checkbox" />
            <span>{{ t("emailSettings.test_mode") }}</span>
          </label>

          <label class="checkbox-row">
            <input v-model="draft.enabled" type="checkbox" />
            <span>{{ t("emailSettings.enabled") }}</span>
          </label>

          <label class="checkbox-row">
            <input v-model="draft.is_default" type="checkbox" />
            <span>{{ t("emailSettings.default_channel") }}</span>
          </label>
        </div>

        <div class="settings-modal-actions">
          <button class="secondary-btn narrow" type="button" @click="closeEditorModal">{{ t("emailSettings.cancel") }}</button>
          <button class="primary-btn narrow" type="button" :disabled="saving" @click="saveEmail">
            {{ saving ? t("emailSettings.saving") : isCreateMode ? t("emailSettings.create_channel_config") : t("emailSettings.save_channel_config") }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
