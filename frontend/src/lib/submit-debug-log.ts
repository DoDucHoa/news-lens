type SubmitDebugLevel = "info" | "warn" | "error";

interface SubmitDebugPayload {
  event: string;
  level?: SubmitDebugLevel;
  data?: Record<string, unknown>;
}

function toSafeRecord(data: unknown): Record<string, unknown> {
  if (!data || typeof data !== "object") {
    return {};
  }

  return data as Record<string, unknown>;
}

export function writeSubmitDebugLog(payload: SubmitDebugPayload): void {
  if (typeof window === "undefined") {
    return;
  }

  const body = {
    event: payload.event,
    level: payload.level ?? "info",
    at: new Date().toISOString(),
    pageUrl: window.location.href,
    userAgent: window.navigator.userAgent,
    data: toSafeRecord(payload.data),
  };

  void fetch("/debug-log", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    keepalive: true,
    body: JSON.stringify(body),
    cache: "no-store",
  }).catch(() => {
    // Avoid throwing from the logging path.
  });
}
