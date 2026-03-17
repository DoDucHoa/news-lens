const STORAGE_KEY = "newslens:query-history:v1";
const MAX_ITEMS = 20;

export interface QueryHistoryItem {
  id: string;
  question: string;
  topK?: number;
  createdAt: string;
}

function canUseSessionStorage(): boolean {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

function safeParse(raw: string | null): QueryHistoryItem[] {
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((item): item is QueryHistoryItem => {
      if (!item || typeof item !== "object") {
        return false;
      }

      const candidate = item as Record<string, unknown>;
      return (
        typeof candidate.id === "string" &&
        typeof candidate.question === "string" &&
        typeof candidate.createdAt === "string" &&
        (typeof candidate.topK === "number" || typeof candidate.topK === "undefined")
      );
    });
  } catch {
    return [];
  }
}

export function getQueryHistory(): QueryHistoryItem[] {
  if (!canUseSessionStorage()) {
    return [];
  }

  return safeParse(window.sessionStorage.getItem(STORAGE_KEY));
}

export function saveQueryHistory(items: QueryHistoryItem[]): void {
  if (!canUseSessionStorage()) {
    return;
  }

  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
}

export function addQueryToHistory(question: string, topK?: number): QueryHistoryItem {
  const normalizedQuestion = question.trim();

  const newItem: QueryHistoryItem = {
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`,
    question: normalizedQuestion,
    topK,
    createdAt: new Date().toISOString(),
  };

  const nextItems = [newItem, ...getQueryHistory()]
    .filter((item, index, all) => all.findIndex((v) => v.question === item.question) === index)
    .slice(0, MAX_ITEMS);

  saveQueryHistory(nextItems);
  return newItem;
}

export function clearQueryHistory(): void {
  if (!canUseSessionStorage()) {
    return;
  }

  window.sessionStorage.removeItem(STORAGE_KEY);
}
