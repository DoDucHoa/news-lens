"use client";

import { type FormEvent, type KeyboardEvent } from "react";

interface QueryInputProps {
  question: string;
  topK: number;
  isLoading: boolean;
  onQuestionChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

export function QueryInput({
  question,
  topK,
  isLoading,
  onQuestionChange,
  onTopKChange,
  onSubmit,
  onCancel,
}: QueryInputProps) {
  const handleFormSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    onSubmit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <form className="news-card fade-up p-5 lg:p-6" onSubmit={handleFormSubmit}>
      <label htmlFor="question" className="subtle-label mb-2 block">
        Ask about the latest news
      </label>
      <textarea
        id="question"
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        rows={6}
        maxLength={6000}
        placeholder="Example: Summarize today's most important AI developments."
        className="control-field w-full resize-y rounded-lg p-3 text-sm leading-6 text-zinc-900 disabled:cursor-not-allowed disabled:opacity-70"
      />

      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="top-k" className="subtle-label">
            Number of top documents to retrieve
          </label>
          <input
            id="top-k"
            type="number"
            min={1}
            max={20}
            value={topK}
            disabled={isLoading}
            onChange={(event) => onTopKChange(Number(event.target.value))}
            className="control-field w-20 rounded-md px-2 py-1 text-sm text-zinc-900 disabled:cursor-not-allowed disabled:opacity-70"
          />
        </div>

        <div className="flex items-center gap-2">
          {isLoading ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100"
            >
              Cancel
            </button>
          ) : null}

          <button
            type="submit"
            disabled={isLoading || question.trim().length === 0}
            className="btn-primary inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:bg-zinc-400"
          >
            {isLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true" />
            ) : null}
            Submit
          </button>
        </div>
      </div>
    </form>
  );
}
