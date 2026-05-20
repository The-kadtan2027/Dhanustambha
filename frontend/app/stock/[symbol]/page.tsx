import StockDetailClient from "./stock-detail-client";
import type { TradesBySymbol } from "../../../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store", headers: { "Content-Type": "application/json" } });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch { return null; }
}

export default async function StockDetailPage(props: { params: Promise<{ symbol: string }> }) {
  const params = await props.params;
  const symbol = params.symbol.toUpperCase();
  const tradeData = await fetchJson<TradesBySymbol>(`/trades/by-symbol/${symbol}`);
  return <StockDetailClient apiBaseUrl={API_BASE_URL} symbol={symbol} initialTradeData={tradeData} />;
}
