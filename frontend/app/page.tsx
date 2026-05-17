import DashboardClient from "./dashboard-client";
import type { Briefing, DateList, TradeList, TradeSummary } from "../types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const [briefing, dates, openTrades, actions, summary] = await Promise.all([
    fetchJson<Briefing>("/briefing/latest"),
    fetchJson<DateList>("/briefing/dates"),
    fetchJson<TradeList>("/trades/open"),
    fetchJson<TradeList>("/trades/actions"),
    fetchJson<TradeSummary>("/trades/summary")
  ]);

  return (
    <DashboardClient
      apiBaseUrl={API_BASE_URL}
      initialActions={actions}
      initialBriefing={briefing}
      initialDates={dates}
      initialOpenTrades={openTrades}
      initialSummary={summary}
    />
  );
}
