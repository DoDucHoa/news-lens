"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { AnswerDisplay } from "@/components/AnswerDisplay";
import { ErrorToast } from "@/components/ErrorToast";
import { QueryInput } from "@/components/QueryInput";
import { SourcesList } from "@/components/SourcesList";
import { StatusBar } from "@/components/StatusBar";
import { ApiClientError, getBackendHealth, queryNews } from "@/lib/api";
import { addQueryToHistory } from "@/lib/session-history";
import { type SourceItem } from "@/lib/types";

type PageState = "idle" | "loading" | "success" | "error" | "cancelled";
type ServiceStatus = "online" | "degraded" | "offline" | "unknown";

interface QueryViewState {
  status: PageState;
  answer: string;
  sources: SourceItem[];
  warning?: string;
  errorMessage: string;
  showErrorToast: boolean;
}

type QueryAction =
  | { type: "submit_start" }
  | { type: "submit_success"; answer: string; sources: SourceItem[]; warning?: string }
  | { type: "submit_error"; message: string }
  | { type: "submit_cancelled" }
  | { type: "dismiss_toast" };

const initialQueryViewState: QueryViewState = {
  status: "idle",
  answer: "",
  sources: [],
  warning: undefined,
  errorMessage: "",
  showErrorToast: false,
};

function queryReducer(state: QueryViewState, action: QueryAction): QueryViewState {
  switch (action.type) {
    case "submit_start":
      return {
        ...state,
        status: "loading",
        answer: "",
        sources: [],
        warning: undefined,
        errorMessage: "",
        showErrorToast: false,
      };
    case "submit_success":
      return {
        ...state,
        status: "success",
        answer: action.answer,
        sources: action.sources,
        warning: action.warning,
        errorMessage: "",
        showErrorToast: false,
      };
    case "submit_error":
      return {
        ...state,
        status: "error",
        errorMessage: action.message,
        showErrorToast: true,
      };
    case "submit_cancelled":
      return {
        ...state,
        status: "cancelled",
        showErrorToast: false,
      };
    case "dismiss_toast":
      return {
        ...state,
        showErrorToast: false,
      };
    default:
      return state;
  }
}

function toServiceStatus(status?: string): ServiceStatus {
  if (status === "healthy") {
    return "online";
  }

  if (status === "degraded") {
    return "degraded";
  }

  if (status === "unhealthy") {
    return "offline";
  }

  return "unknown";
}

function readFallbackAnswer(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readFallbackSources(value: unknown): SourceItem[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is SourceItem => Boolean(item && typeof item === "object" && typeof (item as SourceItem).url === "string"))
    .map((item) => ({
      url: item.url,
      title: typeof item.title === "string" ? item.title : "",
      date: typeof item.date === "string" ? item.date : "",
      snippet: typeof item.snippet === "string" ? item.snippet : "",
      score: typeof item.score === "number" ? item.score : 0,
      source_name: typeof item.source_name === "string" ? item.source_name : "",
    }));
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const [queryState, dispatch] = useReducer(queryReducer, initialQueryViewState);
  const [backendStatus, setBackendStatus] = useState<ServiceStatus>("unknown");
  const [ollamaStatus, setOllamaStatus] = useState<ServiceStatus>("unknown");
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState<string>();

  const abortRef = useRef<AbortController | null>(null);

  const isLoading = queryState.status === "loading";
  const isEmptyRetrieval =
    !isLoading &&
    queryState.answer.trim().length === 0 &&
    queryState.sources.length === 0 &&
    queryState.status === "success";

  const closeToast = useCallback(() => {
    dispatch({ type: "dismiss_toast" });
  }, []);

  const resolveUserMessage = useCallback((error: unknown): string => {
    if (!(error instanceof ApiClientError)) {
      return "Unexpected failure happened. Please try again.";
    }

    if (error.kind === "timeout") {
      return "Request timed out after one retry. Please shorten the prompt or try again.";
    }

    if (error.kind === "server" || (typeof error.status === "number" && error.status >= 500)) {
      return "Backend returned a 5xx error. Please wait a moment and retry.";
    }

    if (error.kind === "network") {
      return "Network or CORS issue detected. Check backend URL and connectivity, then retry.";
    }

    if (error.kind === "parse") {
      return "Response format mismatch detected. Please retry while backend/frontend contracts are checked.";
    }

    if (error.kind === "client") {
      return "Request was rejected by backend. Please review query input and top_k value.";
    }

    return error.message || "Unable to process your request. Please try again.";
  }, []);

  const refreshStatus = useCallback(async () => {
    setIsCheckingStatus(true);

    try {
      const health = await getBackendHealth({ timeoutMs: 5000 });
      const backend = toServiceStatus(health.status);

      setBackendStatus(backend);
      // Backend health is used as inferred Ollama readiness in MVP.
      setOllamaStatus(backend === "online" ? "online" : backend === "degraded" ? "degraded" : "unknown");
      setLastCheckedAt(new Date().toLocaleTimeString());
    } catch {
      setBackendStatus("offline");
      setOllamaStatus("unknown");
      setLastCheckedAt(new Date().toLocaleTimeString());
    } finally {
      setIsCheckingStatus(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
    const intervalId = window.setInterval(() => void refreshStatus(), 30000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [refreshStatus]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const submitQuery = useCallback(async () => {
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion || isLoading) {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    addQueryToHistory(normalizedQuestion, topK);
    dispatch({ type: "submit_start" });

    try {
      const payload = await queryNews(
        {
          question: normalizedQuestion,
          top_k: topK,
        },
        {
          signal: controller.signal,
          timeoutMs: 15000,
        },
      );

      const answerText = payload.full?.answer ?? readFallbackAnswer(payload.partial?.answer);
      const sourceItems = payload.full?.sources ?? readFallbackSources(payload.partial?.sources);

      dispatch({
        type: "submit_success",
        answer: answerText,
        sources: sourceItems,
        warning: payload.warning,
      });

    } catch (error) {
      if (error instanceof ApiClientError && error.kind === "aborted") {
        dispatch({ type: "submit_cancelled" });
        return;
      }

      dispatch({ type: "submit_error", message: resolveUserMessage(error) });
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, [isLoading, question, resolveUserMessage, topK]);

  const cancelQuery = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const pageHint = useMemo(() => {
    if (queryState.status === "cancelled") {
      return "Request cancelled.";
    }

    if (queryState.status === "error") {
      return "Request failed. You can adjust the prompt and submit again.";
    }

    return "Press Enter to submit. Use Shift+Enter for a new line.";
  }, [queryState.status]);

  return (
    <main className="min-h-screen text-zinc-900">
      <div className="news-shell flex w-full flex-col gap-4">
        <header className="news-card fade-up px-5 py-5 lg:px-7">
          <p className="subtle-label mb-2">Local RAG Newsroom</p>
          <h1 className="news-headline text-3xl leading-tight tracking-tight">News Lens</h1>
          <p className="mt-2 max-w-3xl text-sm ink-muted">
            Ask questions about recent news and get concise answers with source links.
          </p>
        </header>

        <StatusBar
          backend={backendStatus}
          ollama={ollamaStatus}
          isRefreshing={isCheckingStatus}
          lastCheckedAt={lastCheckedAt}
        />

        <QueryInput
          question={question}
          topK={topK}
          isLoading={isLoading}
          onQuestionChange={setQuestion}
          onTopKChange={(value) => setTopK(Number.isFinite(value) && value >= 1 && value <= 20 ? value : 5)}
          onSubmit={() => {
            void submitQuery();
          }}
          onCancel={cancelQuery}
        />

        <p className="px-1 text-xs ink-muted">{pageHint}</p>

        <div className="grid gap-4 lg:grid-cols-[1.45fr_1fr]">
          <AnswerDisplay
            answer={queryState.answer}
            isLoading={isLoading}
            warning={queryState.warning}
            isEmptyRetrieval={isEmptyRetrieval}
          />
          <SourcesList sources={queryState.sources} isLoading={isLoading} />
        </div>
      </div>

      <ErrorToast
        visible={queryState.showErrorToast}
        message={queryState.errorMessage}
        onClose={closeToast}
      />
    </main>
  );
}
