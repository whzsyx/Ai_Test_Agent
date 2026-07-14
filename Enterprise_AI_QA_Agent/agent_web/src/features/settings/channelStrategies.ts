import { t } from "../../services/i18n";
import type {
  ChannelConfigCreateRequest,
  ChannelConfigPublic,
  ChannelDomain,
  ChannelProvider,
  ChannelStatus,
} from "../../types";

export type ChannelForm = {
  config_name: string;
  enabled: boolean;
  app_id: string;
  account_id: string;
  app_secret: string;
  token: string;
  sandbox_mode: boolean;
  connection_mode: string;
  description: string;
  clear_credentials: boolean;
};

export type ChannelField =
  | {
      kind: "text" | "password";
      key: keyof ChannelForm;
      labelKey: string;
      placeholder?: string;
      autocomplete?: string;
    }
  | {
      kind: "select";
      key: keyof ChannelForm;
      labelKey: string;
      options: Array<{ value: string; labelKey: string }>;
    }
  | {
      kind: "switch";
      key: keyof ChannelForm;
      labelKey: string;
      hintKey: string;
    };

export type ChannelDefinition = {
  domain: ChannelDomain;
  provider: ChannelProvider;
  labelKey: string;
  summaryKey: string;
  icon: string;
  secretField: "app_secret" | "token";
};

export interface ChannelStrategy {
  definition: ChannelDefinition;
  supportsPairing: boolean;
  panelEyebrowKey: string;
  manualSummaryKey: string;
  pairingTitleKey: string;
  pairingDescriptionKey: string;
  unavailablePairingKey?: string;
  defaultName(): string;
  statusLabel(status?: ChannelStatus): string;
  applyConfig(form: ChannelForm, config: ChannelConfigPublic | null): void;
  publicConfig(form: ChannelForm): Record<string, unknown>;
  credentials(form: ChannelForm): Record<string, string> | null;
  manualFields(hasStoredSecret: boolean): ChannelField[];
  buildPayload(form: ChannelForm): ChannelConfigCreateRequest;
}

const channelDefinitions: Record<ChannelDomain, ChannelDefinition> = {
  qq: {
    domain: "qq",
    provider: "qq",
    labelKey: "channels.qq",
    summaryKey: "channels.qq_desc",
    icon: "fa-brands fa-qq",
    secretField: "app_secret",
  },
  feishu: {
    domain: "feishu",
    provider: "feishu",
    labelKey: "channels.feishu",
    summaryKey: "channels.feishu_desc",
    icon: "fa-solid fa-paper-plane",
    secretField: "app_secret",
  },
  lark: {
    domain: "lark",
    provider: "feishu",
    labelKey: "channels.lark",
    summaryKey: "channels.lark_desc",
    icon: "fa-solid fa-globe",
    secretField: "app_secret",
  },
  weixin: {
    domain: "weixin",
    provider: "weixin",
    labelKey: "channels.weixin",
    summaryKey: "channels.weixin_desc",
    icon: "fa-brands fa-weixin",
    secretField: "token",
  },
};

export const channelOrder: ChannelDomain[] = ["qq", "feishu", "lark", "weixin"];

export const channelStrategies: Record<ChannelDomain, ChannelStrategy> = {
  qq: makeQQStrategy(),
  feishu: makeFeishuStrategy("feishu"),
  lark: makeFeishuStrategy("lark"),
  weixin: makeWeixinStrategy(),
};

export function getChannelStrategy(domain: ChannelDomain): ChannelStrategy {
  return channelStrategies[domain] || channelStrategies.qq;
}

export function createEmptyChannelForm(): ChannelForm {
  return {
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
  };
}

function makeQQStrategy(): ChannelStrategy {
  const definition = channelDefinitions.qq;
  return baseStrategy({
    definition,
    supportsPairing: false,
    panelEyebrowKey: "channels.qq_manual_first",
    manualSummaryKey: "channels.qq_official_config",
    pairingTitleKey: "channels.qq_official_config",
    pairingDescriptionKey: "channels.qq_no_qr",
    unavailablePairingKey: "channels.qq_no_qr",
    statusLabel(status) {
      if (status === "configured") return t("channels.status_qq_configured");
      if (status === "disabled") return t("channels.status_disabled");
      return t("channels.status_qq_unconfigured");
    },
    applySpecific(form, config) {
      form.app_id = readPublicText(config, "app_id");
      form.sandbox_mode = config?.public_config?.sandbox_mode === true;
      form.app_secret = "";
    },
    publicConfig(form) {
      return { app_id: form.app_id.trim(), sandbox_mode: form.sandbox_mode };
    },
    credentials(form) {
      return form.app_secret.trim() ? { app_secret: form.app_secret.trim() } : null;
    },
    manualFields(hasStoredSecret) {
      return [
        { kind: "text", key: "app_id", labelKey: "channels.app_id", placeholder: "App ID" },
        { kind: "switch", key: "sandbox_mode", labelKey: "channels.sandbox_mode", hintKey: "channels.sandbox_mode_desc" },
        {
          kind: "password",
          key: "app_secret",
          labelKey: "channels.app_secret",
          placeholder: hasStoredSecret ? t("channels.secret_saved_ph") : t("channels.secret_ph"),
          autocomplete: "new-password",
        },
      ];
    },
  });
}

function makeFeishuStrategy(domain: "feishu" | "lark"): ChannelStrategy {
  const definition = channelDefinitions[domain];
  return baseStrategy({
    definition,
    supportsPairing: true,
    panelEyebrowKey: "channels.scan_first",
    manualSummaryKey: "channels.advanced_manual",
    pairingTitleKey: "channels.scan_bind_title",
    pairingDescriptionKey: domain === "lark" ? "channels.lark_pairing_desc" : "channels.feishu_pairing_desc",
    applySpecific(form, config) {
      form.app_id = readPublicText(config, "app_id");
      form.connection_mode = readPublicText(config, "connection_mode") || "event_callback";
      form.app_secret = "";
    },
    publicConfig(form) {
      return { app_id: form.app_id.trim(), connection_mode: form.connection_mode };
    },
    credentials(form) {
      return form.app_secret.trim() ? { app_secret: form.app_secret.trim() } : null;
    },
    manualFields(hasStoredSecret) {
      return [
        { kind: "text", key: "app_id", labelKey: "channels.app_id", placeholder: "App ID" },
        {
          kind: "select",
          key: "connection_mode",
          labelKey: "channels.connection_mode",
          options: [
            { value: "event_callback", labelKey: "channels.mode_event_callback" },
            { value: "webhook", labelKey: "channels.mode_webhook" },
            { value: "websocket", labelKey: "channels.mode_websocket" },
            { value: "reserved", labelKey: "channels.mode_reserved" },
          ],
        },
        {
          kind: "password",
          key: "app_secret",
          labelKey: "channels.app_secret",
          placeholder: hasStoredSecret ? t("channels.secret_saved_ph") : t("channels.secret_ph"),
          autocomplete: "new-password",
        },
      ];
    },
  });
}

function makeWeixinStrategy(): ChannelStrategy {
  const definition = channelDefinitions.weixin;
  return baseStrategy({
    definition,
    supportsPairing: true,
    panelEyebrowKey: "channels.scan_first",
    manualSummaryKey: "channels.advanced_manual",
    pairingTitleKey: "channels.scan_bind_title",
    pairingDescriptionKey: "channels.weixin_pairing_desc",
    applySpecific(form, config) {
      form.account_id = readPublicText(config, "account_id");
      form.token = "";
    },
    publicConfig(form) {
      return { account_id: form.account_id.trim() };
    },
    credentials(form) {
      return form.token.trim() ? { token: form.token.trim() } : null;
    },
    manualFields(hasStoredSecret) {
      return [
        { kind: "text", key: "account_id", labelKey: "channels.account_id", placeholder: "gh_xxxxxxxx" },
        {
          kind: "password",
          key: "token",
          labelKey: "channels.token",
          placeholder: hasStoredSecret ? t("channels.secret_saved_ph") : t("channels.secret_ph"),
          autocomplete: "new-password",
        },
      ];
    },
  });
}

function baseStrategy(options: {
  definition: ChannelDefinition;
  supportsPairing: boolean;
  panelEyebrowKey: string;
  manualSummaryKey: string;
  pairingTitleKey: string;
  pairingDescriptionKey: string;
  unavailablePairingKey?: string;
  statusLabel?: (status?: ChannelStatus) => string;
  applySpecific: (form: ChannelForm, config: ChannelConfigPublic | null) => void;
  publicConfig: (form: ChannelForm) => Record<string, unknown>;
  credentials: (form: ChannelForm) => Record<string, string> | null;
  manualFields: (hasStoredSecret: boolean) => ChannelField[];
}): ChannelStrategy {
  return {
    definition: options.definition,
    supportsPairing: options.supportsPairing,
    panelEyebrowKey: options.panelEyebrowKey,
    manualSummaryKey: options.manualSummaryKey,
    pairingTitleKey: options.pairingTitleKey,
    pairingDescriptionKey: options.pairingDescriptionKey,
    unavailablePairingKey: options.unavailablePairingKey,
    defaultName() {
      return `${t(options.definition.labelKey)} ${t("channels.config_suffix")}`;
    },
    statusLabel(status) {
      if (options.statusLabel) return options.statusLabel(status);
      if (status === "configured") return t("channels.status_configured");
      if (status === "disabled") return t("channels.status_disabled");
      return t("channels.status_unconfigured");
    },
    applyConfig(form, config) {
      form.config_name = config?.config_name || this.defaultName();
      form.enabled = config?.enabled || false;
      form.app_id = "";
      form.account_id = "";
      form.app_secret = "";
      form.token = "";
      form.sandbox_mode = false;
      form.connection_mode = "event_callback";
      form.description = config?.description || "";
      form.clear_credentials = false;
      options.applySpecific(form, config);
    },
    publicConfig: options.publicConfig,
    credentials: options.credentials,
    manualFields: options.manualFields,
    buildPayload(form) {
      return {
        config_name: form.config_name.trim() || this.defaultName(),
        provider: options.definition.provider,
        domain: options.definition.domain,
        enabled: form.enabled,
        public_config: options.publicConfig(form),
        credentials: options.credentials(form),
        description: form.description.trim() || null,
      };
    },
  };
}

function readPublicText(config: ChannelConfigPublic | null, key: string): string {
  const value = config?.public_config?.[key];
  return value === undefined || value === null ? "" : String(value);
}
