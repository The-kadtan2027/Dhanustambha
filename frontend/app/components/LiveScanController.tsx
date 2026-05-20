"use client";

import { useState, useEffect } from "react";
import { fetchJson } from "../../lib/api";

type LiveScanControllerProps = {
  apiBaseUrl: string;
  onComplete: () => void;
  label?: string;
};

export default function LiveScanController({ 
  apiBaseUrl, 
  onComplete,
  label = "Live Scan 🚀"
}: LiveScanControllerProps) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function startScan() {
    try {
      setError(null);
      const data = await fetchJson<{ job_id: string }>(apiBaseUrl, '/briefing/live/start', { method: 'POST' });
      setJobId(data.job_id);
      setStatus('running');
      setProgress(0);
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') return;

    const interval = setInterval(async () => {
      try {
        const data = await fetchJson<any>(apiBaseUrl, `/briefing/live/status/${jobId}`);
        setStatus(data.status);
        setProgress(data.progress);
        if (data.status === 'completed') {
          clearInterval(interval);
          onComplete();
        } else if (data.status === 'failed') {
          clearInterval(interval);
          setError(data.error);
        }
      } catch (err) {
        console.error('Failed to poll status:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, status, apiBaseUrl, onComplete]);

  if (!jobId && !error) {
    return (
      <button 
        className="textButton" 
        style={{ background: 'var(--blue)', color: 'white', padding: '6px 14px', borderRadius: '6px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
        onClick={startScan}
      >
        {label}
      </button>
    );
  }

  return (
    <div className="liveScanPill" style={{ width: '100%', maxWidth: '600px' }}>
      <h4 style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>
          {status === 'completed' ? 'Scan Completed ✅' : status === 'failed' ? 'Scan Failed ❌' : 'Live Scan in Progress 🚀'}
        </span>
        {(status === 'completed' || status === 'failed') && (
          <button className="textButton" onClick={() => { setJobId(null); setStatus(null); setProgress(0); setError(null); }} style={{ fontSize: '11px' }}>
            Dismiss
          </button>
        )}
      </h4>
      <p>
        {status === 'running' && `Fetching OHLCV for all symbols...`}
        {status === 'processing_breadth' && `Computing market breadth...`}
        {status === 'scanning' && `Running setup scanners...`}
        {status === 'completed' && `Fresh candidates found. Page refreshed.`}
        {status === 'failed' && `Error: ${error}`}
      </p>
      <div className="progressContainer">
        <div className="progressBar" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
