import MarketClient from "./market-client";
import type { Market } from "../../types/api";

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

export default async function MarketPage() {
  const [latest, history] = await Promise.all([
    fetchJson<Market>("/market/breadth/latest"),
    fetchJson<{ count: number; items: Market[] }>("/market/breadth/history?days=90")
  ]);

  return (
    <MarketClient
      apiBaseUrl={API_BASE_URL}
      initialHistory={history?.items ?? []}
      initialMarket={latest}
    />
  );
}
