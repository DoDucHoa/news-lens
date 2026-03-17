"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [warning, setWarning] = useState<string | undefined>(undefined);
  const [pageState, setPageState] = useState<PageState>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [showErrorToast, setShowErrorToast] = useState(false);
  const [backendStatus, setBackendStatus] = useState<ServiceStatus>("unknown");
  const [ollamaStatus, setOllamaStatus] = useState<ServiceStatus>("unknown");
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState<string>();

  const abortRef = useRef<AbortController | null>(null);

  const isLoading = pageState === "loading";
  const isEmptyRetrieval = !isLoading && answer.trim().length === 0 && sources.length === 0 && pageState === "success";

  const closeToast = useCallback(() => {
    setShowErrorToast(false);
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

    setPageState("loading");
    setShowErrorToast(false);
    setErrorMessage("");
    setWarning(undefined);

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

      if (payload.full) {
        setAnswer(payload.full.answer);
        setSources(payload.full.sources);
      } else {
        setAnswer(readFallbackAnswer(payload.partial?.answer));
        setSources(readFallbackSources(payload.partial?.sources));
      }

      setWarning(payload.warning);
      addQueryToHistory(normalizedQuestion, topK);
      setPageState("success");
    } catch (error) {
      if (error instanceof ApiClientError && error.kind === "aborted") {
        setPageState("cancelled");
        return;
      }

      let message = "Unable to process your request. Please try again.";
      if (error instanceof ApiClientError) {
        if (error.kind === "timeout") {
          message = "Request timed out after one retry. Please try again.";
        } else if (error.kind === "server" || (typeof error.status === "number" && error.status >= 500)) {
          message = "Server error occurred. Please try again in a moment.";
        } else if (error.message) {
          message = error.message;
        }
      }

      setErrorMessage(message);
      setShowErrorToast(true);
      setPageState("error");
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }, [isLoading, question, topK]);

  const cancelQuery = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const pageHint = useMemo(() => {
    if (pageState === "cancelled") {
      return "Request cancelled.";
    }

    if (pageState === "error") {
      return "Request failed. You can adjust the prompt and submit again.";
    }

    return "Press Enter to submit. Use Shift+Enter for a new line.";
  }, [pageState]);

  return (
    <main className="min-h-screen bg-zinc-100 px-4 py-8 text-zinc-900">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
        <header className="rounded-xl border border-zinc-200 bg-white px-5 py-4 shadow-sm">
          <h1 className="text-2xl font-semibold tracking-tight">News Lens</h1>
          <p className="mt-1 text-sm text-zinc-600">
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

        <p className="px-1 text-xs text-zinc-500">{pageHint}</p>

        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <AnswerDisplay
            answer={answer}
            isLoading={isLoading}
            warning={warning}
            isEmptyRetrieval={isEmptyRetrieval}
          />
          <SourcesList sources={sources} isLoading={isLoading} />
        </div>
      </div>

      <ErrorToast
        visible={showErrorToast}
        message={errorMessage}
        onClose={closeToast}
      />
    </main>
  );
}
