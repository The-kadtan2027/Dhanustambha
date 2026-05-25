"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  type CandlestickSeriesOptions,
  type IChartApi,
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
  title?: string;
  subtitle?: string;
};

function formatVol(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function formatPrice(v: number): string {
  return `Rs ${v.toFixed(2)}`;
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
  title,
  subtitle,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [crosshair, setCrosshair] = useState<CrosshairData | null>(null);
  const candleMapRef = useRef<Map<string, Candle>>(new Map());

  useEffect(() => {
    candleMapRef.current = new Map(candles.map((candle) => [candle.time, candle]));
  }, [candles]);

  const handleCrosshairMove = useCallback(
    (param: { time?: unknown }) => {
      if (!param.time) {
        setCrosshair(null);
        return;
      }
      const dateStr =
        typeof param.time === "number"
          ? new Date(param.time * 1000).toISOString().slice(0, 10)
          : String(param.time);
      const candle = candleMapRef.current.get(dateStr);
      if (!candle) return;
      setCrosshair({
        date: dateStr,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
        ma20: candle.ma20,
        ma50: candle.ma50,
        isUp: candle.close >= candle.open,
      });
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
        vertLines: { color: "rgba(23, 32, 42, 0.05)" },
        horzLines: { color: "rgba(23, 32, 42, 0.05)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: "rgba(23, 32, 42, 0.12)",
      },
      timeScale: {
        borderColor: "rgba(23, 32, 42, 0.12)",
        timeVisible: true,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    } as Partial<CandlestickSeriesOptions>);
    candleSeries.setData(
      candles.map((candle) => ({
        time: candle.time as Parameters<typeof candleSeries.setData>[0][number]["time"],
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }))
    );

    if (signalDate) {
      const signalCandle = candleMapRef.current.get(signalDate);
      if (signalCandle) {
        candleSeries.createPriceLine({
          price: signalCandle.low * 0.997,
          color: setupBadgeColor(setupType),
          lineWidth: 1,
          lineStyle: 1,
          axisLabelVisible: true,
          title: `Signal ${setupShortLabel(setupType)}`,
        });
      }
    }

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    volumeSeries.setData(
      candles.map((candle) => ({
        time: candle.time as Parameters<typeof volumeSeries.setData>[0][number]["time"],
        value: candle.volume,
        color: candle.close >= candle.open ? "rgba(34,197,94,0.45)" : "rgba(239,68,68,0.45)",
      }))
    );

    const ma20Series = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma20Series.setData(
      candles
        .filter((candle) => candle.ma20 !== null)
        .map((candle) => ({
          time: candle.time as Parameters<typeof ma20Series.setData>[0][number]["time"],
          value: candle.ma20 as number,
        }))
    );

    const ma50Series = chart.addSeries(LineSeries, {
      color: "#818cf8",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ma50Series.setData(
      candles
        .filter((candle) => candle.ma50 !== null)
        .map((candle) => ({
          time: candle.time as Parameters<typeof ma50Series.setData>[0][number]["time"],
          value: candle.ma50 as number,
        }))
    );

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
    chart.subscribeCrosshairMove((param) => handleCrosshairMove(param));

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, entryPrice, handleCrosshairMove, height, setupType, signalDate, stopPrice]);

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
  const activeCandle = crosshair ?? (() => {
    const last = candles[candles.length - 1];
    if (!last) return null;
    return {
      date: last.time,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      volume: last.volume,
      ma20: last.ma20,
      ma50: last.ma50,
      isUp: last.close >= last.open,
    };
  })();
  const visibleHigh = candles.reduce(
    (acc, candle) => Math.max(acc, candle.high),
    Number.NEGATIVE_INFINITY
  );
  const visibleLow = candles.reduce(
    (acc, candle) => Math.min(acc, candle.low),
    Number.POSITIVE_INFINITY
  );
  const lastCandle = candles[candles.length - 1];
  const ma20Gap = lastCandle?.ma20 != null ? lastCandle.close - lastCandle.ma20 : null;
  const ma50Gap = lastCandle?.ma50 != null ? lastCandle.close - lastCandle.ma50 : null;

  return (
    <div className="chartShell" style={{ marginTop: "12px", position: "relative" }}>
      <div className="chartSummaryBand">
        <div>
          <div className="chartSummaryTitle">{title ?? "Price Structure"}</div>
          <div className="chartSummaryDate">
            {activeCandle?.date ?? "-"}
            {subtitle ? ` · ${subtitle}` : crosshair ? " · Hover" : " · Latest"}
          </div>
        </div>
        <div className="chartSummaryStats">
          <span className={`chartStat ${activeCandle?.isUp ? "up" : "down"}`}>
            C {activeCandle ? formatPrice(activeCandle.close) : "-"}
          </span>
          <span className="chartStat">
            Range {Number.isFinite(visibleLow) && Number.isFinite(visibleHigh)
              ? `${formatPrice(visibleLow)}-${formatPrice(visibleHigh)}`
              : "-"}
          </span>
          <span className="chartStat">Vol {activeCandle ? formatVol(activeCandle.volume) : "-"}</span>
          {ma20Gap !== null && (
            <span className={`chartStat ${ma20Gap >= 0 ? "up" : "down"}`}>
              vs MA20 {ma20Gap >= 0 ? "+" : ""}{ma20Gap.toFixed(2)}
            </span>
          )}
          {ma50Gap !== null && (
            <span className={`chartStat ${ma50Gap >= 0 ? "up" : "down"}`}>
              vs MA50 {ma50Gap >= 0 ? "+" : ""}{ma50Gap.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      <div className="chartLegendRow">
        <span style={{ color: "#f59e0b" }}>- MA20</span>
        <span style={{ color: "#818cf8" }}>- MA50</span>
        {signalDate && setupType && (
          <span style={{ color: setupBadgeColor(setupType) }}>Signal {signalDate}</span>
        )}
        {entryPrice && <span style={{ color: "#22c55e" }}>Entry {formatPrice(entryPrice)}</span>}
        {stopPrice && stopPrice > 0 && (
          <span style={{ color: "#ef4444" }}>Stop {formatPrice(stopPrice)}</span>
        )}
        {riskPct && <span style={{ color: "#ef4444", opacity: 0.7 }}>Risk {riskPct}%</span>}
        {setupType && (
          <span className="chartSetupBadge" style={{ background: setupBadgeColor(setupType) }}>
            {setupShortLabel(setupType)}
          </span>
        )}
      </div>

      <div style={{ position: "relative" }}>
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
