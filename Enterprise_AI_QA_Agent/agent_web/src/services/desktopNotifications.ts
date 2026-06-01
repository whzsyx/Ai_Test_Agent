/**
 * Desktop Notification Service (Service Worker based).
 *
 * Uses Service Worker's showNotification() for reliable notifications
 * that work even when the tab is in background or minimized.
 *
 * Monitors session events and triggers browser notifications when:
 * - A session completes while the user is away.
 * - An approval is required while the user is away.
 *
 * Respects the user's general settings for notification preferences.
 */
import { useGeneralSettingsStore } from "../stores/generalSettings";

const notifiedIds = new Set<string>();
let swRegistration: ServiceWorkerRegistration | null = null;

/**
 * Register the Service Worker. Call once at app startup.
 */
export async function registerServiceWorker(): Promise<void> {
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

/**
 * Get the active SW registration (lazy).
 */
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

/**
 * Determine if the user is "away" from the current session.
 * Away means: tab not visible, OR user is not on the Home page.
 */
function isUserAway(_sessionId?: string): boolean {
  // Tab not visible (user switched to another app/tab).
  if (document.visibilityState !== "visible") {
    return true;
  }
  // User navigated away from the home/chat page within the app.
  const path = window.location.pathname || "";
  if (!path.endsWith("/") && path !== "/" && !path.includes("/home")) {
    return true;
  }
  return false;
}

/**
 * Send a desktop notification via Service Worker.
 * Falls back to basic Notification API if SW is not available.
 */
async function sendNotification(title: string, options?: NotificationOptions): Promise<void> {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }

  const reg = await getRegistration();
  if (reg) {
    // Use Service Worker showNotification (works in background).
    try {
      await reg.showNotification(title, {
        icon: "/logo.svg",
        badge: "/logo.svg",
        tag: options?.tag || "default",
        ...options,
      } as NotificationOptions);
      return;
    } catch {
      // Fall through to basic API.
    }
  }

  // Fallback: basic Notification API.
  try {
    const notification = new Notification(title, {
      icon: "/logo.svg",
      ...options,
    });
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
    setTimeout(() => notification.close(), 8000);
  } catch {
    // Notification API may fail in some contexts.
  }
}

/**
 * Check and notify for session completion.
 */
export function notifySessionComplete(sessionId: string, title?: string): void {
  const settings = useGeneralSettingsStore();
  console.log("[Notifications] notifySessionComplete called", {
    sessionId,
    notifyEnabled: settings.notifySessionCompleteWhenAway,
    canSend: settings.canSendDesktopNotifications,
    awayOnly: settings.notificationsAwayOnly,
    isAway: isUserAway(sessionId),
    permission: typeof Notification !== "undefined" ? Notification.permission : "N/A",
  });

  if (!settings.notifySessionCompleteWhenAway) return;
  if (!settings.canSendDesktopNotifications) return;
  if (settings.notificationsAwayOnly && !isUserAway(sessionId)) return;

  const notifyKey = `session_complete_${sessionId}`;
  if (notifiedIds.has(notifyKey)) return;
  notifiedIds.add(notifyKey);

  console.log("[Notifications] Sending notification:", title);
  void sendNotification("会话执行完成", {
    body: title || `会话 ${sessionId.slice(0, 8)} 已完成执行。`,
    tag: notifyKey,
  });
}

/**
 * Check and notify for pending approval.
 */
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
      ? `工具 "${toolName}" 需要审批才能继续执行。`
      : "有工具操作需要您的审批。",
    tag: notifyKey,
  });
}

/**
 * Clear notification history (e.g., on session switch).
 */
export function clearNotificationHistory(): void {
  notifiedIds.clear();
}
