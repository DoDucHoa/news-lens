import {
  type ApiErrorEnvelope,
  type ApiErrorKind,
  type ApiRequestOptions,
  type HealthResponse,
  type ParsedQueryPayload,
  type PartialQueryResponse,
  type QueryRequest,
  type SourceItem,
} from "@/lib/types";
import { emitTelemetry } from "@/lib/telemetry";

const DEFAULT_TIMEOUT_MS = 15000;
const DEFAULT_RETRY_COUNT = 1;

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

export function resolveApiBaseUrl(): string {
  const mode = process.env.NEXT_PUBLIC_API_MODE ?? "hybrid";
  const directUrl = normalizeBaseUrl(
    process.env.NEXT_PUBLIC_API_DIRECT_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001",
  );
  const proxyPath = normalizeBaseUrl(process.env.NEXT_PUBLIC_API_PROXY_PATH ?? "/api");

  if (mode === "direct") {
    return directUrl;
  }

  if (mode === "proxy") {
    return proxyPath;
  }

  if (typeof window === "undefined") {
    return normalizeBaseUrl(process.env.INTERNAL_API_URL ?? directUrl);
  }

  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  return isLocal ? directUrl : proxyPath;
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

  try {
    const response = await fetch(toUrl(path), {
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
      throw new ApiClientError({
        message: extractErrorMessage(response.status, payload),
        kind: classifyHttpError(response.status),
        status: response.status,
        payload,
      });
    }

    const json = (await safeParseJson(response)) as T | null;
    if (json === null) {
      throw new ApiClientError({
        message: "Response is not valid JSON",
        kind: "parse",
        status: response.status,
      });
    }

    return json;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      const isUserAbort = options.signal?.aborted === true;
      const isTimeout = !isUserAbort;

      if (isTimeout && retryCount > 0) {
        return requestJson<T>(path, init, options, retryCount - 1);
      }

      throw new ApiClientError({
        message: isUserAbort ? "Request cancelled by user" : "Request timed out",
        kind: isUserAbort ? "aborted" : "timeout",
      });
    }

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

function parseQueryPayload(payload: unknown): ParsedQueryPayload {
  if (!payload || typeof payload !== "object") {
    return {
      full: null,
      partial: null,
      warning: "Response payload is not an object",
    };
  }

  const record = payload as PartialQueryResponse;
  const answer = record.answer;
  const sources = record.sources;
  const queryTime = record.query_time_ms;

  const answerValid = typeof answer === "string";
  const sourcesValid = Array.isArray(sources) && sources.every((item) => isSourceItem(item));
  const queryTimeValid = typeof queryTime === "number";

  if (answerValid && sourcesValid && queryTimeValid) {
    return {
      full: {
        answer,
        sources,
        query_time_ms: queryTime,
      },
      partial: record,
    };
  }

  const warning = "Response schema drift detected; rendering with partial data.";

  return {
    full: null,
    partial: record,
    warning,
  };
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
