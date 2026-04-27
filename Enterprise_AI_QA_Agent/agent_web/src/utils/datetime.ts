const ISO_WITHOUT_TZ_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;

function normalizeServerDate(value?: string | null): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "";
  }
  return ISO_WITHOUT_TZ_PATTERN.test(normalized) ? `${normalized}Z` : normalized;
}

export function parseServerDate(value?: string | null): Date | null {
  const normalized = normalizeServerDate(value);
  if (!normalized) {
    return null;
  }
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatServerDateTime(value?: string | null, fallback = "--"): string {
  const parsed = parseServerDate(value);
  if (!parsed) {
    return String(value || fallback);
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

export function formatServerTime(value?: string | null, fallback = "--"): string {
  const parsed = parseServerDate(value);
  if (!parsed) {
    return String(value || fallback);
  }
  return parsed.toLocaleTimeString("zh-CN", { hour12: false });
}

export function serverDateTimestamp(value?: string | null): number {
  return parseServerDate(value)?.getTime() ?? 0;
}
