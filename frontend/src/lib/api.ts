import {
  type ApiErrorEnvelope,
  type ApiErrorKind,
  type ApiRequestOptions,
  type HealthResponse,
  type ParsedQueryPayload,
  type PartialQueryResponse,
  type QueryStreamCompleteEvent,
  type QueryStreamErrorEvent,
  type QueryStreamHandlers,
  type QueryStreamServerEvent,
  type QueryStreamSourcesEvent,
  type QueryStreamStatusEvent,
  type QueryStreamTokenEvent,
  type QueryStreamWarningEvent,
  type QueryRequest,
  type SourceItem,
} from "@/lib/types";
import { emitTelemetry } from "@/lib/telemetry";
import { writeSubmitDebugLog } from "@/lib/submit-debug-log";

const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_RETRY_COUNT = 1;

function toWebSocketBaseUrl(httpBase: string): string {
  if (httpBase.startsWith("https://")) {
    return `wss://${httpBase.slice("https://".length)}`;
  }

  if (httpBase.startsWith("http://")) {
    return `ws://${httpBase.slice("http://".length)}`;
  }

  return httpBase;
}

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly payload?: ApiErrorEnvelope;

  constructor(params: {
    message: string;
    kind: ApiErrorKind;
    status?: number;
    payload?: ApiErrorEnvelope;
  }) {
    super(params.message);
    this.name = "ApiClientError";
    this.kind = params.kind;
    this.status = params.status;
    this.payload = params.payload;
  }
}

function normalizeBaseUrl(input: string): string {
  if (!input) {
    return "";
  }

  return input.endsWith("/") ? input.slice(0, -1) : input;
}

function isLocalHostName(host: string): boolean {
  return host === "localhost" || host === "127.0.0.1" || host === "::1";
}

function isLoopbackHttpUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return isLocalHostName(parsed.hostname);
  } catch {
    return false;
  }
}

function normalizeProxyPath(input: string): string {
  if (!input) {
    return "/api";
  }

  const normalized = normalizeBaseUrl(input);
  return normalized.startsWith("/") ? normalized : `/${normalized}`;
}

function resolveBrowserDirectApiBaseUrl(): string {
  const configuredDirect = normalizeBaseUrl(
    process.env.NEXT_PUBLIC_API_DIRECT_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001",
  );

  if (typeof window === "undefined") {
    return configuredDirect;
  }

  if (!isLoopbackHttpUrl(configuredDirect)) {
    return configuredDirect;
  }

  if (isLocalHostName(window.location.hostname)) {
    // Keep localhost/127.0.0.1 development behavior exactly as configured.
    return configuredDirect;
  }

  const protocol = window.location.protocol === "https:" ? "https" : "http";
  const backendPort = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8001";
  return `${protocol}://${window.location.hostname}:${backendPort}`;
}

export function resolveApiBaseUrl(): string {
  const mode = process.env.NEXT_PUBLIC_API_MODE ?? "hybrid";
  const directUrl = resolveBrowserDirectApiBaseUrl();
  const proxyPath = normalizeProxyPath(process.env.NEXT_PUBLIC_API_PROXY_PATH ?? "/api");

  if (typeof window !== "undefined") {
    const currentHostIsLocal = isLocalHostName(window.location.hostname);
    const directPointsToLoopback = isLoopbackHttpUrl(directUrl);

    if (mode === "direct") {
      // Guardrail for misconfigured deployments where direct URL is localhost on a public host.
      if (!currentHostIsLocal && directPointsToLoopback) {
        return proxyPath;
      }

      return directUrl;
    }

    if (mode === "proxy") {
      return proxyPath;
    }

    return currentHostIsLocal ? directUrl : proxyPath;
  }

  return normalizeBaseUrl(process.env.INTERNAL_API_URL ?? directUrl);
}

export function resolveRealtimeWebSocketUrl(): string {
  const explicit = normalizeBaseUrl(process.env.NEXT_PUBLIC_WS_URL ?? "");
  if (explicit) {
    return `${explicit}/ws/query`;
  }

  const apiBase = resolveApiBaseUrl();

  if (apiBase.startsWith("http://") || apiBase.startsWith("https://")) {
    const wsBase = toWebSocketBaseUrl(apiBase);
    return `${wsBase}/ws/query`;
  }

  if (typeof window !== "undefined") {
    // Prefer direct WS host for reliability across runtimes where rewrite/proxy WS upgrades may not be enabled.
    const directWsBase = toWebSocketBaseUrl(resolveBrowserDirectApiBaseUrl());
    return `${directWsBase}/ws/query`;
  }

  const directUrl = normalizeBaseUrl(
    process.env.NEXT_PUBLIC_API_DIRECT_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001",
  );
  return `${toWebSocketBaseUrl(directUrl)}/ws/query`;
}

function toUrl(path: string): string {
  const base = resolveApiBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (!base) {
    return normalizedPath;
  }

  if (base.startsWith("http://") || base.startsWith("https://")) {
    return `${base}${normalizedPath}`;
  }

  const normalizedBase = base.startsWith("/") ? base : `/${base}`;
  return `${normalizedBase}${normalizedPath}`;
}

function buildAbortSignal(timeoutMs: number, externalSignal?: AbortSignal): {
  signal: AbortSignal;
  cleanup: () => void;
} {
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => {
    timeoutController.abort("timeout");
  }, timeoutMs);

  let detachExternal = (): void => undefined;

  if (externalSignal) {
    const onExternalAbort = (): void => {
      timeoutController.abort("aborted");
    };

    if (externalSignal.aborted) {
      onExternalAbort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
      detachExternal = () => {
        externalSignal.removeEventListener("abort", onExternalAbort);
      };
    }
  }

  return {
    signal: timeoutController.signal,
    cleanup: () => {
      clearTimeout(timeoutId);
      detachExternal();
    },
  };
}

async function safeParseJson(response: Response): Promise<unknown | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return (await response.json()) as unknown;
  } catch {
    return null;
  }
}

function parseApiEnvelope(payload: unknown): ApiErrorEnvelope | undefined {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }

  return payload as ApiErrorEnvelope;
}

function classifyHttpError(status: number): ApiErrorKind {
  if (status >= 500) {
    return "server";
  }

  if (status >= 400) {
    return "client";
  }

  return "unknown";
}

function extractErrorMessage(status: number, payload?: ApiErrorEnvelope): string {
  if (payload?.detail && typeof payload.detail === "string") {
    return payload.detail;
  }

  if (payload?.message && typeof payload.message === "string") {
    return payload.message;
  }

  if (payload?.error && typeof payload.error === "string") {
    return payload.error;
  }

  return `Request failed with status ${status}`;
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  options: ApiRequestOptions = {},
  retryCount = DEFAULT_RETRY_COUNT,
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const { signal, cleanup } = buildAbortSignal(timeoutMs, options.signal);
  const url = toUrl(path);

  writeSubmitDebugLog({
    event: "api_request_start",
    data: {
      path,
      url,
      method: init.method ?? "GET",
      timeoutMs,
      retryCount,
      mode: process.env.NEXT_PUBLIC_API_MODE ?? "hybrid",
    },
  });

  try {
    const response = await fetch(url, {
      ...init,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const payload = parseApiEnvelope(await safeParseJson(response));
      writeSubmitDebugLog({
        event: "api_request_http_error",
        level: "warn",
        data: {
          path,
          url,
          status: response.status,
          payload,
        },
      });

      throw new ApiClientError({
        message: extractErrorMessage(response.status, payload),
        kind: classifyHttpError(response.status),
        status: response.status,
        payload,
      });
    }

    const json = (await safeParseJson(response)) as T | null;
    if (json === null) {
      writeSubmitDebugLog({
        event: "api_response_parse_error",
        level: "warn",
        data: {
          path,
          url,
          status: response.status,
          contentType: response.headers.get("content-type") ?? "",
        },
      });

      throw new ApiClientError({
        message: "Response is not valid JSON",
        kind: "parse",
        status: response.status,
      });
    }

    writeSubmitDebugLog({
      event: "api_request_success",
      data: {
        path,
        url,
        status: response.status,
      },
    });

    return json;
  } catch (error) {
    if (error instanceof ApiClientError) {
      writeSubmitDebugLog({
        event: "api_client_error",
        level: "warn",
        data: {
          path,
          url,
          kind: error.kind,
          status: error.status ?? null,
          message: error.message,
        },
      });

      throw error;
    }

    const abortReason = typeof error === "string" ? error : undefined;
    if (abortReason === "timeout" || abortReason === "aborted") {
      const isUserAbort = abortReason === "aborted" || options.signal?.aborted === true;
      const isTimeout = !isUserAbort;

      if (isTimeout && retryCount > 0) {
        writeSubmitDebugLog({
          event: "api_retry_timeout",
          level: "warn",
          data: {
            path,
            url,
            remainingRetry: retryCount,
          },
        });

        return requestJson<T>(path, init, options, retryCount - 1);
      }

      writeSubmitDebugLog({
        event: "api_abort",
        level: "warn",
        data: {
          path,
          url,
          isUserAbort,
          isTimeout,
        },
      });

      throw new ApiClientError({
        message: isUserAbort ? "Request cancelled by user" : "Request timed out",
        kind: isUserAbort ? "aborted" : "timeout",
      });
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      const isUserAbort = options.signal?.aborted === true;
      const isTimeout = !isUserAbort;

      if (isTimeout && retryCount > 0) {
        writeSubmitDebugLog({
          event: "api_retry_timeout",
          level: "warn",
          data: {
            path,
            url,
            remainingRetry: retryCount,
          },
        });

        return requestJson<T>(path, init, options, retryCount - 1);
      }

      writeSubmitDebugLog({
        event: "api_abort",
        level: "warn",
        data: {
          path,
          url,
          isUserAbort,
          isTimeout,
        },
      });

      throw new ApiClientError({
        message: isUserAbort ? "Request cancelled by user" : "Request timed out",
        kind: isUserAbort ? "aborted" : "timeout",
      });
    }

    if (error instanceof TypeError) {
      if (retryCount > 0) {
        writeSubmitDebugLog({
          event: "api_retry_network",
          level: "warn",
          data: {
            path,
            url,
            remainingRetry: retryCount,
            name: error.name,
            message: error.message,
          },
        });

        return requestJson<T>(path, init, options, retryCount - 1);
      }

      writeSubmitDebugLog({
        event: "api_type_error",
        level: "error",
        data: {
          path,
          url,
          name: error.name,
          message: error.message,
        },
      });

      throw new ApiClientError({
        message: "Network/CORS error while contacting backend",
        kind: "network",
      });
    }

    writeSubmitDebugLog({
      event: "api_unknown_error",
      level: "error",
      data: {
        path,
        url,
        name: error instanceof Error ? error.name : typeof error,
        message: error instanceof Error ? error.message : "unknown",
      },
    });

    throw new ApiClientError({
      message: error instanceof Error ? error.message : "Unknown network error",
      kind: "network",
    });
  } finally {
    cleanup();
  }
}

function isSourceItem(candidate: unknown): candidate is SourceItem {
  if (!candidate || typeof candidate !== "object") {
    return false;
  }

  const item = candidate as Record<string, unknown>;
  return (
    typeof item.url === "string" &&
    typeof item.title === "string" &&
    typeof item.date === "string" &&
    typeof item.snippet === "string" &&
    typeof item.score === "number" &&
    typeof item.source_name === "string"
  );
}

function firstNumber(record: Record<string, unknown>, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (typeof value === "string") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return undefined;
}

function firstString(record: Record<string, unknown>, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }

  return undefined;
}

function normalizeSource(candidate: unknown): SourceItem | null {
  if (typeof candidate === "string" && candidate.trim().length > 0) {
    return {
      url: candidate,
      title: "",
      date: "",
      snippet: "",
      score: 0,
      source_name: "",
    };
  }

  if (!candidate || typeof candidate !== "object") {
    return null;
  }

  const record = candidate as Record<string, unknown>;
  const urlValue =
    (typeof record.url === "string" && record.url) ||
    (typeof record.link === "string" && record.link) ||
    (typeof record.href === "string" && record.href) ||
    "";

  if (!urlValue) {
    return null;
  }

  const score =
    typeof record.score === "number"
      ? record.score
      : typeof record.relevance === "number"
        ? record.relevance
        : 0;

  return {
    url: urlValue,
    title: typeof record.title === "string" ? record.title : "",
    date: typeof record.date === "string" ? record.date : typeof record.published_at === "string" ? record.published_at : "",
    snippet: typeof record.snippet === "string" ? record.snippet : typeof record.summary === "string" ? record.summary : "",
    score,
    source_name: typeof record.source_name === "string" ? record.source_name : typeof record.source === "string" ? record.source : "",
  };
}

function normalizeSources(raw: unknown): SourceItem[] {
  if (!raw) {
    return [];
  }

  if (Array.isArray(raw)) {
    return raw
      .map((item) => normalizeSource(item))
      .filter((item): item is SourceItem => item !== null);
  }

  if (typeof raw === "object") {
    const record = raw as Record<string, unknown>;
    const nested = Array.isArray(record.items)
      ? record.items
      : Array.isArray(record.sources)
        ? record.sources
        : Array.isArray(record.documents)
          ? record.documents
          : null;

    if (nested) {
      return nested
        .map((item) => normalizeSource(item))
        .filter((item): item is SourceItem => item !== null);
    }
  }

  return [];
}

function parseQueryPayload(payload: unknown): ParsedQueryPayload {
  if (!payload || typeof payload !== "object") {
    return {
      full: null,
      partial: null,
      warning: "Response payload is not an object",
    };
  }

  const record = payload as PartialQueryResponse;
  const recordLike = payload as Record<string, unknown>;

  let normalizedAnswer = firstString(recordLike, [
    "answer",
    "response",
    "result",
    "generated_answer",
    "text",
  ]);

  const rawSources =
    recordLike.sources ??
    recordLike.source_items ??
    recordLike.references ??
    recordLike.docs ??
    recordLike.documents;

  const normalizedSources = normalizeSources(rawSources);
  const normalizedQueryTime = firstNumber(recordLike, ["query_time_ms", "latency_ms", "queryTimeMs"]);

  if (!normalizedAnswer && normalizedSources.length > 0) {
    normalizedAnswer = "Model returned no textual answer for this request. Please review the retrieved sources below or retry.";
  }

  const normalizedAnswerSafe = normalizedAnswer ?? "";
  const answerValid = normalizedAnswerSafe.length > 0;
  const sourcesValid = Array.isArray(normalizedSources) && normalizedSources.every((item) => isSourceItem(item));
  const queryTimeValid = typeof normalizedQueryTime === "number";

  if (answerValid && sourcesValid && queryTimeValid) {
    return {
      full: {
        answer: normalizedAnswerSafe,
        sources: normalizedSources,
        query_time_ms: normalizedQueryTime,
      },
      partial: {
        ...record,
        answer: normalizedAnswerSafe,
        sources: normalizedSources,
        query_time_ms: normalizedQueryTime,
      },
    };
  }

  const missing: string[] = [];
  if (!answerValid) {
    missing.push("answer");
  }
  if (!sourcesValid || normalizedSources.length === 0) {
    missing.push("sources");
  }
  if (!queryTimeValid) {
    missing.push("query_time_ms");
  }

  const warning = `Response schema drift detected; rendering partial data. Missing: ${missing.join(", ")}.`;

  return {
    full: null,
    partial: {
      ...record,
      answer: normalizedAnswerSafe,
      sources: normalizedSources,
      query_time_ms: normalizedQueryTime,
    },
    warning,
  };
}

function parseStreamEvent(payload: unknown): QueryStreamServerEvent | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Record<string, unknown>;
  const type = record.type;
  if (typeof type !== "string") {
    return null;
  }

  switch (type) {
    case "status":
      return {
        type: "status",
        stage: typeof record.stage === "string" ? record.stage : "unknown",
        message: typeof record.message === "string" ? record.message : "",
        timestamp: typeof record.timestamp === "string" ? record.timestamp : undefined,
      };
    case "token":
      return {
        type: "token",
        token: typeof record.token === "string" ? record.token : "",
        timestamp: typeof record.timestamp === "string" ? record.timestamp : undefined,
      };
    case "sources":
      return {
        type: "sources",
        sources: record.sources,
        timestamp: typeof record.timestamp === "string" ? record.timestamp : undefined,
      };
    case "warning":
      return {
        type: "warning",
        message: typeof record.message === "string" ? record.message : "",
        timestamp: typeof record.timestamp === "string" ? record.timestamp : undefined,
      };
    case "error":
      return {
        type: "error",
        message: typeof record.message === "string" ? record.message : "Unknown websocket error",
        recoverable: typeof record.recoverable === "boolean" ? record.recoverable : undefined,
        timestamp: typeof record.timestamp === "string" ? record.timestamp : undefined,
      };
    case "complete":
      return {
        type: "complete",
        answer: typeof record.answer === "string" ? record.answer : undefined,
        sources: record.sources,
        query_time_ms: typeof record.query_time_ms === "number" ? record.query_time_ms : undefined,
        timestamp: typeof record.timestamp === "string" ? record.timestamp : undefined,
      };
    default:
      return null;
  }
}

export async function queryNewsRealtime(
  request: QueryRequest,
  handlers: QueryStreamHandlers = {},
  options: ApiRequestOptions = {},
): Promise<ParsedQueryPayload> {
  const startedAt = performance.now();
  const timeoutMs = options.timeoutMs ?? 120000;
  const wsUrl = resolveRealtimeWebSocketUrl();

  emitTelemetry("query_submit", {
    transport: "websocket",
    has_top_k: typeof request.top_k === "number",
    question_length: request.question.length,
  });

  return new Promise<ParsedQueryPayload>((resolve, reject) => {
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
    } catch {
      reject(
        new ApiClientError({
          message: "Failed to initialize websocket connection",
          kind: "network",
        }),
      );
      return;
    }

    let settled = false;
    let completed = false;
    let aggregatedAnswer = "";
    let latestWarning: string | undefined;
    let latestSources: SourceItem[] = [];
    let queryTimeMs = 0;
    let abortedByUser = false;

    const timeoutId = window.setTimeout(() => {
      if (settled) {
        return;
      }

      settled = true;
      try {
        ws.close(4000, "timeout");
      } catch {
        // Ignore close errors during timeout cleanup.
      }

      reject(
        new ApiClientError({
          message: "Realtime request timed out",
          kind: "timeout",
        }),
      );
    }, timeoutMs);

    const abortListener = () => {
      if (settled) {
        return;
      }

      abortedByUser = true;
      settled = true;
      try {
        ws.close(4001, "aborted");
      } catch {
        // Ignore close errors during abort cleanup.
      }

      reject(
        new ApiClientError({
          message: "Request cancelled by user",
          kind: "aborted",
        }),
      );
    };

    if (options.signal) {
      if (options.signal.aborted) {
        abortListener();
      } else {
        options.signal.addEventListener("abort", abortListener, { once: true });
      }
    }

    const cleanup = () => {
      window.clearTimeout(timeoutId);
      if (options.signal) {
        options.signal.removeEventListener("abort", abortListener);
      }
    };

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: "query",
          question: request.question,
          top_k: request.top_k,
          llm_model: request.llm_model,
        }),
      );
    };

    ws.onmessage = (messageEvent) => {
      if (settled) {
        return;
      }

      let rawPayload: unknown;
      try {
        rawPayload = JSON.parse(messageEvent.data as string) as unknown;
      } catch {
        return;
      }

      const event = parseStreamEvent(rawPayload);
      if (!event) {
        return;
      }

      if (event.type === "status") {
        handlers.onStatus?.(event as QueryStreamStatusEvent);
        return;
      }

      if (event.type === "token") {
        const tokenEvent = event as QueryStreamTokenEvent;
        aggregatedAnswer += tokenEvent.token;
        handlers.onToken?.(tokenEvent, aggregatedAnswer);
        return;
      }

      if (event.type === "sources") {
        const sourceEvent = event as QueryStreamSourcesEvent;
        latestSources = normalizeSources(sourceEvent.sources);
        handlers.onSources?.(latestSources);
        return;
      }

      if (event.type === "warning") {
        const warningEvent = event as QueryStreamWarningEvent;
        latestWarning = warningEvent.message;
        handlers.onWarning?.(warningEvent);
        return;
      }

      if (event.type === "error") {
        const errorEvent = event as QueryStreamErrorEvent;
        handlers.onError?.(errorEvent);
        settled = true;
        cleanup();
        try {
          ws.close();
        } catch {
          // Ignore close errors while handling server-side failure.
        }

        reject(
          new ApiClientError({
            message: errorEvent.message,
            kind: errorEvent.recoverable ? "client" : "server",
          }),
        );
        return;
      }

      if (event.type === "complete") {
        const completeEvent = event as QueryStreamCompleteEvent;
        completed = true;
        if (typeof completeEvent.answer === "string" && completeEvent.answer.trim().length > 0) {
          aggregatedAnswer = completeEvent.answer;
        }

        if (typeof completeEvent.query_time_ms === "number") {
          queryTimeMs = completeEvent.query_time_ms;
        }

        if (completeEvent.sources !== undefined) {
          latestSources = normalizeSources(completeEvent.sources);
          handlers.onSources?.(latestSources);
        }

        settled = true;
        cleanup();
        try {
          ws.close(1000, "completed");
        } catch {
          // Ignore close errors during completion.
        }

        const measuredLatency = Math.round(performance.now() - startedAt);
        const resolvedQueryTime = queryTimeMs > 0 ? queryTimeMs : measuredLatency;

        emitTelemetry("query_latency_ms", { value: measuredLatency });
        emitTelemetry("query_success", {
          latency_ms: measuredLatency,
          schema_warning: Boolean(latestWarning),
          transport: "websocket",
        });

        resolve({
          full: {
            answer: aggregatedAnswer,
            sources: latestSources,
            query_time_ms: resolvedQueryTime,
          },
          partial: {
            answer: aggregatedAnswer,
            sources: latestSources,
            query_time_ms: resolvedQueryTime,
          },
          warning: latestWarning,
        });
      }
    };

    ws.onerror = () => {
      if (settled) {
        return;
      }

      settled = true;
      cleanup();
      reject(
        new ApiClientError({
          message: "WebSocket connection error while contacting backend",
          kind: "network",
        }),
      );
    };

    ws.onclose = () => {
      if (settled) {
        return;
      }

      settled = true;
      cleanup();

      if (abortedByUser) {
        reject(
          new ApiClientError({
            message: "Request cancelled by user",
            kind: "aborted",
          }),
        );
        return;
      }

      if (completed) {
        return;
      }

      reject(
        new ApiClientError({
          message: "WebSocket connection closed before completion",
          kind: "network",
        }),
      );
    };
  });
}

export async function queryNews(
  request: QueryRequest,
  options: ApiRequestOptions = {},
): Promise<ParsedQueryPayload> {
  const startedAt = performance.now();
  emitTelemetry("query_submit", {
    has_top_k: typeof request.top_k === "number",
    question_length: request.question.length,
  });

  try {
    const payload = await requestJson<unknown>(
      "/query",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      options,
      DEFAULT_RETRY_COUNT,
    );

    const parsed = parseQueryPayload(payload);
    const latency = Math.round(performance.now() - startedAt);

    emitTelemetry("query_latency_ms", { value: latency });
    emitTelemetry("query_success", {
      latency_ms: latency,
      schema_warning: Boolean(parsed.warning),
    });

    return parsed;
  } catch (error) {
    const latency = Math.round(performance.now() - startedAt);
    const reason = error instanceof ApiClientError ? error.kind : "unknown";

    emitTelemetry("query_latency_ms", { value: latency });
    emitTelemetry("query_failure", {
      latency_ms: latency,
      reason,
    });

    throw error;
  }
}

export async function getBackendHealth(
  options: ApiRequestOptions = {},
): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health", { method: "GET" }, options, 0);
}
