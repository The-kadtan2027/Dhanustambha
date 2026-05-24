"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type CandlestickSeriesOptions,
  ColorType,
  CrosshairMode,
} from "lightweight-charts";

export type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma20: number | null;
  ma50: number | null;
};

type CrosshairData = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma20: number | null;
  ma50: number | null;
  isUp: boolean;
};

type Props = {
  candles: Candle[];
  entryPrice?: number | null;
  stopPrice?: number | null;
  height?: number;
  setupType?: string | null;
  signalDate?: string | null;
};

function formatVol(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function formatPrice(v: number): string {
  return `₹${v.toFixed(2)}`;
}

function setupBadgeColor(setupType: string | null | undefined): string {
  if (!setupType) return "#94a3b8";
  if (setupType.includes("MOMENTUM")) return "#f59e0b";
  if (setupType.includes("EPISODIC") || setupType === "EP") return "#818cf8";
  if (setupType.includes("TREND")) return "#22c55e";
  return "#94a3b8";
}

function setupShortLabel(setupType: string | null | undefined): string {
  if (!setupType) return "";
  if (setupType.includes("MOMENTUM")) return "MB";
  if (setupType.includes("EPISODIC") || setupType === "EP") return "EP";
  if (setupType.includes("TREND")) return "TI";
  return setupType.slice(0, 3);
}

export default function CandleChart({
  candles,
  entryPrice,
  stopPrice,
  height = 280,
  setupType,
  signalDate,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [crosshair, setCrosshair] = useState<CrosshairData | null>(null);

  // Build a lookup map: date → candle for fast crosshair resolution
  const candleMapRef = useRef<Map<string, Candle>>(new Map());

  useEffect(() => {
    candleMapRef.current = new Map(candles.map((c) => [c.time, c]));
  }, [candles]);

  const handleCrosshairMove = useCallback(
    (param: { time?: unknown; seriesData?: Map<unknown, unknown> }) => {
      if (!param.time) {
        setCrosshair(null);
        return;
      }
      const dateStr = typeof param.time === "number"
        ? new Date(param.time * 1000).toISOString().slice(0, 10)
        : String(param.time);
      const c = candleMapRef.current.get(dateStr);
      if (c) {
        setCrosshair({
          date: dateStr,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
          ma20: c.ma20,
          ma50: c.ma50,
          isUp: c.close >= c.open,
        });
      }
    },
    []
  );

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontFamily: "'Inter', 'DM Sans', system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.08)",
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.08)",
        timeVisible: true,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
    });
    chartRef.current = chart;

    // --- Candlestick series ---
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    } as Partial<CandlestickSeriesOptions>);
    candleSeries.setData(
      candles.map((c) => ({
        time: c.time as Parameters<typeof candleSeries.setData>[0][number]["time"],
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // --- Signal date marker: draw a colored price line at the signal candle's low ---
    // (lightweight-charts v5 removed setMarkers from ISeriesApi; use createPriceLine instead)
    if (signalDate) {
      const markerColor = setupBadgeColor(setupType);
      const markerLabel = setupShortLabel(setupType);
      const signalCandle = candleMapRef.current.get(signalDate);
      if (signalCandle) {
        candleSeries.createPriceLine({
          price: signalCandle.low * 0.997, // just below the wick
          color: markerColor,
          lineWidth: 1,
          lineStyle: 1, // dotted
          axisLabelVisible: true,
          title: `▲ ${markerLabel}`,
        });
      }
    }

    // --- Volume histogram (colored by candle direction) ---
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    volumeSeries.setData(
      candles.map((c) => ({
        time: c.time as Parameters<typeof volumeSeries.setData>[0][number]["time"],
        value: c.volume,
        // Green for up-candles, red for down — standard trading convention
        color: c.close >= c.open ? "rgba(34,197,94,0.45)" : "rgba(239,68,68,0.45)",
      }))
    );

    // --- MA20 line (amber) ---
    const ma20Series = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma20Series.setData(
      candles
        .filter((c) => c.ma20 !== null)
        .map((c) => ({
          time: c.time as Parameters<typeof ma20Series.setData>[0][number]["time"],
          value: c.ma20 as number,
        }))
    );

    // --- MA50 line (indigo) ---
    const ma50Series = chart.addSeries(LineSeries, {
      color: "#818cf8",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma50Series.setData(
      candles
        .filter((c) => c.ma50 !== null)
        .map((c) => ({
          time: c.time as Parameters<typeof ma50Series.setData>[0][number]["time"],
          value: c.ma50 as number,
        }))
    );

    // --- Entry price dashed line (green) ---
    if (entryPrice) {
      candleSeries.createPriceLine({
        price: entryPrice,
        color: "#22c55e",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Entry",
      });
    }

    // --- Stop loss dashed line (red) ---
    if (stopPrice && stopPrice > 0) {
      candleSeries.createPriceLine({
        price: stopPrice,
        color: "#ef4444",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Stop",
      });
    }

    chart.timeScale().fitContent();

    // Crosshair data panel handler
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    chart.subscribeCrosshairMove((param: any) => handleCrosshairMove(param));

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, entryPrice, stopPrice, height, setupType, signalDate, handleCrosshairMove]);

  if (candles.length === 0) {
    return (
      <div style={{ color: "var(--text-muted, #64748b)", fontSize: "12px", padding: "8px 0" }}>
        No chart data available.
      </div>
    );
  }

  const showRiskZone = entryPrice && stopPrice && stopPrice > 0 && entryPrice > stopPrice;
  const riskPct = showRiskZone
    ? (((entryPrice - stopPrice) / entryPrice) * 100).toFixed(2)
    : null;

  return (
    <div style={{ marginTop: "12px", position: "relative" }}>
      {/* Legend row */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          fontSize: "11px",
          color: "#94a3b8",
          marginBottom: "4px",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <span style={{ color: "#f59e0b" }}>— MA20</span>
        <span style={{ color: "#818cf8" }}>— MA50</span>
        {entryPrice && <span style={{ color: "#22c55e" }}>-- Entry {formatPrice(entryPrice)}</span>}
        {stopPrice && stopPrice > 0 && (
          <span style={{ color: "#ef4444" }}>-- Stop {formatPrice(stopPrice)}</span>
        )}
        {riskPct && (
          <span style={{ color: "#ef4444", opacity: 0.7 }}>Risk {riskPct}%</span>
        )}
        {setupType && (
          <span
            style={{
              background: setupBadgeColor(setupType),
              color: "#0f172a",
              fontWeight: 700,
              fontSize: "10px",
              padding: "1px 5px",
              borderRadius: "3px",
              marginLeft: "auto",
            }}
          >
            {setupShortLabel(setupType)}
          </span>
        )}
      </div>

      {/* Chart container relative wrapper for overlay */}
      <div style={{ position: "relative" }}>
        {/* Crosshair floating data panel */}
        {crosshair && (
          <div
            style={{
              position: "absolute",
              top: 6,
              left: 6,
              zIndex: 10,
              background: "rgba(15,23,42,0.92)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "6px",
              padding: "6px 10px",
              fontSize: "11px",
              lineHeight: "1.7",
              pointerEvents: "none",
              minWidth: "140px",
              backdropFilter: "blur(4px)",
            }}
          >
            <div style={{ color: "#94a3b8", marginBottom: "3px", fontWeight: 600 }}>
              {crosshair.date}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: "8px" }}>
              <span style={{ color: "#64748b" }}>O</span>
              <span style={{ color: crosshair.isUp ? "#22c55e" : "#ef4444" }}>
                {formatPrice(crosshair.open)}
              </span>
              <span style={{ color: "#64748b" }}>H</span>
              <span style={{ color: "#22c55e" }}>{formatPrice(crosshair.high)}</span>
              <span style={{ color: "#64748b" }}>L</span>
              <span style={{ color: "#ef4444" }}>{formatPrice(crosshair.low)}</span>
              <span style={{ color: "#64748b" }}>C</span>
              <span
                style={{
                  color: crosshair.isUp ? "#22c55e" : "#ef4444",
                  fontWeight: 700,
                }}
              >
                {formatPrice(crosshair.close)}
              </span>
              <span style={{ color: "#64748b" }}>Vol</span>
              <span style={{ color: "#94a3b8" }}>{formatVol(crosshair.volume)}</span>
              {crosshair.ma20 !== null && (
                <>
                  <span style={{ color: "#f59e0b" }}>MA20</span>
                  <span style={{ color: "#f59e0b" }}>{formatPrice(crosshair.ma20)}</span>
                </>
              )}
              {crosshair.ma50 !== null && (
                <>
                  <span style={{ color: "#818cf8" }}>MA50</span>
                  <span style={{ color: "#818cf8" }}>{formatPrice(crosshair.ma50)}</span>
                </>
              )}
            </div>
          </div>
        )}

        <div ref={containerRef} style={{ width: "100%", height: `${height}px` }} />
      </div>
    </div>
  );
}
