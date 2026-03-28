export interface QueryRequest {
  question: string;
  top_k?: number;
  llm_model?: "qwen3.5:0.8b" | "qwen3.5:2b" | "qwen3.5:4b";
}

export interface SourceItem {
  url: string;
  title: string;
  date: string;
  snippet: string;
  score: number;
  source_name: string;
}

export interface QueryResponse {
  answer: string;
  sources: SourceItem[];
  query_time_ms: number;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy" | string;
  chromadb_connected: boolean;
  collection_count: number;
  error?: string | null;
}

export interface PartialQueryResponse {
  answer?: unknown;
  sources?: unknown;
  query_time_ms?: unknown;
  [key: string]: unknown;
}

export interface ApiErrorEnvelope {
  detail?: string | { message?: string; [key: string]: unknown };
  message?: string;
  error?: string;
  [key: string]: unknown;
}

export type ApiErrorKind =
  | "timeout"
  | "aborted"
  | "network"
  | "server"
  | "client"
  | "parse"
  | "unknown";

export interface ApiRequestOptions {
  timeoutMs?: number;
  signal?: AbortSignal;
}

export type QueryStage =
  | "connected"
  | "query_started"
  | "embedding"
  | "retrieval"
  | "generation"
  | "completed"
  | string;

export interface QueryStreamStatusEvent {
  type: "status";
  stage: QueryStage;
  message: string;
  timestamp?: string;
}

export interface QueryStreamTokenEvent {
  type: "token";
  token: string;
  timestamp?: string;
}

export interface QueryStreamSourcesEvent {
  type: "sources";
  sources: unknown;
  timestamp?: string;
}

export interface QueryStreamWarningEvent {
  type: "warning";
  message: string;
  timestamp?: string;
}

export interface QueryStreamErrorEvent {
  type: "error";
  message: string;
  recoverable?: boolean;
  timestamp?: string;
}

export interface QueryStreamCompleteEvent {
  type: "complete";
  answer?: string;
  sources?: unknown;
  query_time_ms?: number;
  timestamp?: string;
}

export type QueryStreamServerEvent =
  | QueryStreamStatusEvent
  | QueryStreamTokenEvent
  | QueryStreamSourcesEvent
  | QueryStreamWarningEvent
  | QueryStreamErrorEvent
  | QueryStreamCompleteEvent;

export interface QueryStreamHandlers {
  onStatus?: (event: QueryStreamStatusEvent) => void;
  onToken?: (event: QueryStreamTokenEvent, aggregatedAnswer: string) => void;
  onSources?: (sources: SourceItem[]) => void;
  onWarning?: (event: QueryStreamWarningEvent) => void;
  onError?: (event: QueryStreamErrorEvent) => void;
}

export interface ParsedQueryPayload {
  full: QueryResponse | null;
  partial: PartialQueryResponse | null;
  warning?: string;
}
