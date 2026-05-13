/**
 * Desktop Notification Service.
 *
 * Monitors session events and triggers browser notifications when:
 * - A session completes while the user is away.
 * - An approval is required while the user is away.
 *
 * Respects the user's general settings for notification preferences.
 */
import { useGeneralSettingsStore } from "../stores/generalSettings";
import { useSessionStore } from "../stores/session";

const notifiedIds = new Set<string>();

/**
 * Determine if the user is "away" from the current interface.
 */
function isUserAway(sessionId?: string): boolean {
  // Tab not visible.
  if (document.visibilityState !== "visible") {
    return true;
  }
  // If a specific session is provided, check if user is on that session.
  if (sessionId) {
    const sessionStore = useSessionStore();
    if (sessionStore.session && sessionStore.session.id !== sessionId) {
      return true;
    }
  }
  return false;
}

/**
 * Send a desktop notification if conditions are met.
 */
function sendNotification(title: string, options?: NotificationOptions): void {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }
  try {
    const notification = new Notification(title, {
      icon: "/favicon.ico",
      badge: "/favicon.ico",
      ...options,
    });
    // Click to focus the window.
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
    // Auto-close after 8 seconds.
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
  if (!settings.notifySessionCompleteWhenAway) return;
  if (!settings.canSendDesktopNotifications) return;
  if (settings.notificationsAwayOnly && !isUserAway(sessionId)) return;

  const notifyKey = `session_complete_${sessionId}`;
  if (notifiedIds.has(notifyKey)) return;
  notifiedIds.add(notifyKey);

  sendNotification("会话执行完成", {
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

  sendNotification("工具审批待处理", {
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
