import TradeClient from "./trade-client";
import type { TradeList } from "../../types/api";

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

export default async function TradesPage() {
  const openTrades = await fetchJson<TradeList>("/trades/open");

  return (
    <TradeClient
      apiBaseUrl={API_BASE_URL}
      initialOpenTrades={openTrades}
    />
  );
}
