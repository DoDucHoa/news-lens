import { appendFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";

import { NextResponse } from "next/server";

export const runtime = "nodejs";

const LOG_DIR = path.join(process.cwd(), "logs");
const LOG_FILE_PATH = path.join(LOG_DIR, "submit-flow-debug.txt");

interface DebugLogRequestBody {
  event?: unknown;
  level?: unknown;
  at?: unknown;
  pageUrl?: unknown;
  userAgent?: unknown;
  data?: unknown;
}

function toStringOrFallback(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim().length > 0 ? value : fallback;
}

function toJsonValue(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return JSON.stringify({ error: "failed_to_stringify" });
  }
}

export async function POST(request: Request): Promise<Response> {
  let payload: DebugLogRequestBody;

  try {
    payload = (await request.json()) as DebugLogRequestBody;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  const time = toStringOrFallback(payload.at, new Date().toISOString());
  const level = toStringOrFallback(payload.level, "info");
  const event = toStringOrFallback(payload.event, "unknown_event");
  const pageUrl = toStringOrFallback(payload.pageUrl, "unknown_page");
  const userAgent = toStringOrFallback(payload.userAgent, "unknown_user_agent");
  const details = toJsonValue(payload.data ?? {});

  const line = `${time} level=${level} event=${event} page=${pageUrl} ua=${userAgent} data=${details}\n`;

  try {
    await mkdir(LOG_DIR, { recursive: true });
    await appendFile(LOG_FILE_PATH, line, "utf8");
    return NextResponse.json({ ok: true, file: "logs/submit-flow-debug.txt" });
  } catch {
    return NextResponse.json({ ok: false, error: "write_failed" }, { status: 500 });
  }
}

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const linesParam = url.searchParams.get("lines");
  const linesRequested = Number(linesParam ?? "100");
  const lines = Number.isFinite(linesRequested) && linesRequested > 0 ? Math.min(linesRequested, 500) : 100;

  try {
    const content = await readFile(LOG_FILE_PATH, "utf8");
    const selected = content.split("\n").filter(Boolean).slice(-lines);
    return NextResponse.json({ ok: true, file: "logs/submit-flow-debug.txt", lines: selected });
  } catch {
    return NextResponse.json({ ok: false, error: "file_not_found" }, { status: 404 });
  }
}
