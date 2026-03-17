"use client";

type ServiceStatus = "online" | "degraded" | "offline" | "unknown";

interface StatusBarProps {
  backend: ServiceStatus;
  ollama: ServiceStatus;
  queryStage?: string;
  realtimeWarning?: string;
  isRefreshing: boolean;
  lastCheckedAt?: string;
}

function badgeClass(status: ServiceStatus): string {
  switch (status) {
    case "online":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "degraded":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "offline":
      return "border-rose-200 bg-rose-50 text-rose-700";
    default:
      return "border-zinc-200 bg-zinc-50 text-zinc-600";
  }
}

function label(status: ServiceStatus): string {
  switch (status) {
    case "online":
      return "Online";
    case "degraded":
      return "Degraded";
    case "offline":
      return "Offline";
    default:
      return "Unknown";
  }
}

function prettyStage(stage?: string): string {
  if (!stage) {
    return "Idle";
  }

  return stage
    .split("_")
    .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1)}` : ""))
    .join(" ");
}

export function StatusBar({ backend, ollama, queryStage, realtimeWarning, isRefreshing, lastCheckedAt }: StatusBarProps) {
  return (
    <section className="news-card fade-up px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-600">
          <span className="rounded-full border px-2 py-1">System status</span>
          <span className={`rounded-full border px-2 py-1 ${badgeClass(backend)}`}>Backend: {label(backend)}</span>
          <span className={`rounded-full border px-2 py-1 ${badgeClass(ollama)}`}>Ollama: {label(ollama)}</span>
          <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-sky-700">Query: {prettyStage(queryStage)}</span>
        </div>

        <div className="text-xs text-zinc-500">
          {isRefreshing ? "Refreshing..." : lastCheckedAt ? `Last checked: ${lastCheckedAt}` : "Waiting for first check"}
        </div>
      </div>

      {realtimeWarning ? (
        <div className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">{realtimeWarning}</div>
      ) : null}
    </section>
  );
}
