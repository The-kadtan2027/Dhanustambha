"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type CandlestickData,
  type LineData,
  type HistogramData,
  ColorType,
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

type Props = {
  candles: Candle[];
  entryPrice?: number | null;
  stopPrice?: number | null;
  height?: number;
};

export default function CandleChart({
  candles,
  entryPrice,
  stopPrice,
  height = 280,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    // Destroy previous instance on re-render
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
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: {
        borderColor: "rgba(255,255,255,0.1)",
        timeVisible: true,
      },
    });
    chartRef.current = chart;

    // --- Candlestick series ---
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    const candleData: CandlestickData[] = candles.map((c) => ({
      time: c.time as unknown as CandlestickData["time"],
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(candleData);

    // --- Volume histogram (secondary scale) ---
    const volumeSeries = chart.addHistogramSeries({
      color: "rgba(100,116,139,0.35)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    const volData: HistogramData[] = candles.map((c) => ({
      time: c.time as unknown as HistogramData["time"],
      value: c.volume,
      color:
        c.close >= c.open
          ? "rgba(34,197,94,0.3)"
          : "rgba(239,68,68,0.3)",
    }));
    volumeSeries.setData(volData);

    // --- MA20 line (amber) ---
    const ma20Series = chart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const ma20Data: LineData[] = candles
      .filter((c) => c.ma20 !== null)
      .map((c) => ({
        time: c.time as unknown as LineData["time"],
        value: c.ma20 as number,
      }));
    ma20Series.setData(ma20Data);

    // --- MA50 line (indigo) ---
    const ma50Series = chart.addLineSeries({
      color: "#818cf8",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const ma50Data: LineData[] = candles
      .filter((c) => c.ma50 !== null)
      .map((c) => ({
        time: c.time as unknown as LineData["time"],
        value: c.ma50 as number,
      }));
    ma50Series.setData(ma50Data);

    // --- Entry price horizontal dashed line (green) ---
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

    // --- Stop loss horizontal dashed line (red) ---
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
  }, [candles, entryPrice, stopPrice, height]);

  if (candles.length === 0) {
    return (
      <div
        style={{
          color: "var(--text-muted, #64748b)",
          fontSize: "12px",
          padding: "8px 0",
        }}
      >
        No chart data available.
      </div>
    );
  }

  return (
    <div style={{ marginTop: "12px" }}>
      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          fontSize: "11px",
          color: "#94a3b8",
          marginBottom: "4px",
        }}
      >
        <span style={{ color: "#f59e0b" }}>— MA20</span>
        <span style={{ color: "#818cf8" }}>— MA50</span>
        {entryPrice && <span style={{ color: "#22c55e" }}>-- Entry</span>}
        {stopPrice && stopPrice > 0 && (
          <span style={{ color: "#ef4444" }}>-- Stop</span>
        )}
      </div>
      <div ref={containerRef} style={{ width: "100%", height: `${height}px` }} />
    </div>
  );
}
