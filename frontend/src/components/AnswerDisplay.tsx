"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AnswerDisplayProps {
  answer: string;
  isLoading: boolean;
  warning?: string;
  isEmptyRetrieval: boolean;
}

export function AnswerDisplay({ answer, isLoading, warning, isEmptyRetrieval }: AnswerDisplayProps) {
  const [copied, setCopied] = useState(false);

  const normalizedAnswer = useMemo(() => answer.trim(), [answer]);

  const handleCopy = async (): Promise<void> => {
    if (!normalizedAnswer) {
      return;
    }

    try {
      await navigator.clipboard.writeText(normalizedAnswer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1300);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="news-card fade-up p-5 lg:p-6">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="section-title">Answer</h2>
        <button
          type="button"
          onClick={handleCopy}
          disabled={!normalizedAnswer || isLoading}
          className="rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {warning ? (
        <div className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">{warning}</div>
      ) : null}

      {isLoading ? (
        <div className="space-y-2" aria-live="polite" aria-busy="true">
          <div className="h-4 w-full animate-pulse rounded bg-zinc-200" />
          <div className="h-4 w-11/12 animate-pulse rounded bg-zinc-200" />
          <div className="h-4 w-4/5 animate-pulse rounded bg-zinc-200" />
          <div className="h-4 w-3/4 animate-pulse rounded bg-zinc-200" />
        </div>
      ) : null}

      {!isLoading && isEmptyRetrieval ? (
        <div className="rounded-md border border-zinc-300 bg-zinc-50 px-3 py-3 text-sm text-zinc-700">
          Not enough data to answer this question confidently. Try adding a time range, source, or topic keyword.
        </div>
      ) : null}

      {!isLoading && !isEmptyRetrieval && normalizedAnswer ? (
        <article className="prose prose-zinc max-w-none text-sm leading-7">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizedAnswer}</ReactMarkdown>
        </article>
      ) : null}

      {!isLoading && !isEmptyRetrieval && !normalizedAnswer ? (
        <p className="text-sm text-zinc-600">Submit a question to see the generated answer.</p>
      ) : null}
    </section>
  );
}
