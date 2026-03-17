"use client";

import { type SourceItem } from "@/lib/types";

interface SourcesListProps {
  sources: SourceItem[];
  isLoading: boolean;
}

export function SourcesList({ sources, isLoading }: SourcesListProps) {
  return (
    <section className="news-card fade-up p-5 lg:p-6">
      <h2 className="section-title mb-3">Sources</h2>

      {isLoading && sources.length === 0 ? (
        <div className="space-y-2" aria-live="polite" aria-busy="true">
          <div className="h-4 w-full animate-pulse rounded bg-zinc-200" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-zinc-200" />
          <div className="h-4 w-4/6 animate-pulse rounded bg-zinc-200" />
        </div>
      ) : null}

      {!isLoading && sources.length === 0 ? (
        <p className="text-sm text-zinc-600">No sources available for this answer yet.</p>
      ) : null}

      {sources.length > 0 ? (
        <ul className="space-y-2 text-sm">
          {sources.map((source, index) => (
            <li key={`${source.url}-${index}`} className="rounded-md border border-zinc-200 bg-zinc-50/80 px-3 py-2">
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="break-words text-zinc-800 underline decoration-zinc-400 underline-offset-2 hover:text-zinc-950"
              >
                {source.url}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
