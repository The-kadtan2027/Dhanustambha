import JournalClient from "./journal-client";
import type { TradeSummary, Trade } from "../../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default async function JournalPage() {
  const [closedTrades, summary] = await Promise.all([
    fetchJson<{count: number; items: Trade[]}>("/trades/closed"),
    fetchJson<TradeSummary>("/trades/summary")
  ]);

  return (
    <JournalClient
      apiBaseUrl={API_BASE_URL}
      initialClosedTrades={closedTrades}
      initialSummary={summary}
    />
  );
}
