/**
 * Desktop notification service.
 *
 * Electron desktop builds use the native main-process Notification API through
 * the preload bridge. Browser builds keep the Service Worker/Notification API
 * fallback.
 */
import { useGeneralSettingsStore } from "../stores/generalSettings";
import removeMarkdown from "remove-markdown";

const notifiedIds = new Set<string>();
let swRegistration: ServiceWorkerRegistration | null = null;

function hasDesktopBridge(): boolean {
  return Boolean(window.qaAgentDesktop?.isDesktop && window.qaAgentDesktop.notify);
}

/**
 * Register the Service Worker. Call once at app startup.
 */
export async function registerServiceWorker(): Promise<void> {
  if (hasDesktopBridge()) {
    return;
  }

  if (!("serviceWorker" in navigator)) {
    console.warn("[Notifications] Service Worker not supported in this browser");
    return;
  }
  try {
    swRegistration = await navigator.serviceWorker.register("/sw.js");
    console.log("[Notifications] Service Worker registered successfully", swRegistration);
  } catch (err) {
    console.warn("[Notifications] SW registration failed:", err);
  }
}

async function getRegistration(): Promise<ServiceWorkerRegistration | null> {
  if (swRegistration) return swRegistration;
  if (!("serviceWorker" in navigator)) return null;
  try {
    swRegistration = await navigator.serviceWorker.ready;
    return swRegistration;
  } catch {
    return null;
  }
}

function isUserAway(_sessionId?: string): boolean {
  if (document.visibilityState !== "visible") {
    return true;
  }

  const path = window.location.pathname || "";
  return !path.endsWith("/") && path !== "/" && !path.includes("/home");
}

function stripMarkdownBody(body?: string): string | undefined {
  if (typeof body !== "string" || !body.trim()) return undefined;
  return removeMarkdown(body, { gfm: true, useImgAltText: true }).trim();
}

async function sendNotification(title: string, options?: NotificationOptions): Promise<void> {
  const plainBody = stripMarkdownBody(options?.body);

  if (hasDesktopBridge()) {
    try {
      await window.qaAgentDesktop?.notify({
        title,
        body: plainBody,
        tag: options?.tag,
        silent: options?.silent,
      });
    } catch (err) {
      console.warn("[Notifications] Native desktop notification failed:", err);
    }
    return;
  }

  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }

  const reg = await getRegistration();
  if (reg) {
    try {
      await reg.showNotification(title, {
        // 不设置 icon，避免在通知左侧显示大图标。
        badge: "/logo.svg",
        tag: options?.tag || "default",
        ...options,
        body: plainBody,
      } as NotificationOptions);
      return;
    } catch {
      // Fall through to the basic Notification API.
    }
  }

  try {
    const notification = new Notification(title, {
      // 不设置 icon，避免在通知左侧显示大图标。
      ...options,
      body: plainBody,
    });
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
    window.setTimeout(() => notification.close(), 8000);
  } catch {
    // Notification API may fail in restricted browser contexts.
  }
}

export interface SessionNotificationOptions {
  title?: string;
  body?: string;
}

export function notifySessionComplete(sessionId: string, options?: SessionNotificationOptions): void {
  const settings = useGeneralSettingsStore();

  if (!settings.notifySessionCompleteWhenAway) return;
  if (!settings.canSendDesktopNotifications) return;
  if (settings.notificationsAwayOnly && !isUserAway(sessionId)) return;

  const notifyKey = `session_complete_${sessionId}`;
  if (notifiedIds.has(notifyKey)) return;
  notifiedIds.add(notifyKey);

  const notifyTitle = options?.title || "会话执行完成";
  const notifyBody = options?.body || `会话 ${sessionId.slice(0, 8)} 已完成执行。`;

  void sendNotification(notifyTitle, {
    body: notifyBody,
    tag: notifyKey,
  });
}

export function notifyApprovalRequired(
  sessionId: string,
  approvalId: string,
  toolName?: string,
): void {
  const settings = useGeneralSettingsStore();
  if (!settings.notifyApprovalRequiredWhenAway) return;
  if (!settings.canSendDesktopNotifications) return;
  if (settings.notificationsAwayOnly && !isUserAway(sessionId)) return;

  const notifyKey = `approval_${approvalId}`;
  if (notifiedIds.has(notifyKey)) return;
  notifiedIds.add(notifyKey);

  void sendNotification("工具审批待处理", {
    body: toolName
      ? `工具 "${toolName}" 需要审批后才能继续执行。`
      : "有工具操作需要您的审批。",
    tag: notifyKey,
  });
}

export function clearNotificationHistory(): void {
  notifiedIds.clear();
}
