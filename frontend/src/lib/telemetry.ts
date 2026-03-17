export type TelemetryEventName =
  | "query_submit"
  | "query_success"
  | "query_failure"
  | "query_latency_ms";

export interface TelemetryEvent {
  name: TelemetryEventName;
  timestamp: number;
  payload?: Record<string, unknown>;
}

const EVENT_TARGET = "newslens:telemetry";

export function emitTelemetry(
  name: TelemetryEventName,
  payload?: Record<string, unknown>,
): void {
  const event: TelemetryEvent = {
    name,
    timestamp: Date.now(),
    payload,
  };

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<TelemetryEvent>(EVENT_TARGET, {
        detail: event,
      }),
    );
  }

  if (process.env.NODE_ENV !== "production") {
    // Keep telemetry observable in local dev without additional tooling.
    console.info("[telemetry]", event);
  }
}

export function onTelemetryEvent(
  handler: (event: TelemetryEvent) => void,
): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  const listener = (evt: Event): void => {
    const custom = evt as CustomEvent<TelemetryEvent>;
    handler(custom.detail);
  };

  window.addEventListener(EVENT_TARGET, listener as EventListener);

  return () => {
    window.removeEventListener(EVENT_TARGET, listener as EventListener);
  };
}
