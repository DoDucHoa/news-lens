export interface QueryRequest {
  question: string;
  top_k?: number;
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

export interface ParsedQueryPayload {
  full: QueryResponse | null;
  partial: PartialQueryResponse | null;
  warning?: string;
}
