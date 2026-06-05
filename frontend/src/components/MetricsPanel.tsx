import React, { useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MetricsData {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  faiss_vectors: number;
  atlas_docs: number;
  daemon_uptime_seconds: number;
  query_count?: number;
  avg_latency_ms?: number;
}

interface MetricsPanelProps {
  /** Latest metrics pushed via WebSocket. Undefined until first event arrives. */
  wsMetrics: MetricsData | undefined;
  /** Whether the WebSocket is currently connected. */
  wsConnected: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 15_000;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatUptime(seconds: number): string {
  if (seconds < 0) return '00:00:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':');
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

// ─── Sub-Components ───────────────────────────────────────────────────────────

/** SVG circular progress ring for CPU usage */
function CpuRing({ percent }: { percent: number }) {
  const radius = 36;
  const stroke = 4;
  const normalised = radius - stroke / 2;
  const circumference = 2 * Math.PI * normalised;
  const offset = circumference * (1 - Math.min(percent, 100) / 100);

  const color =
    percent > 85
      ? 'var(--accent-danger)'
      : percent > 60
        ? 'var(--accent-warning)'
        : 'var(--accent-primary)';

  return (
    <div style={{ position: 'relative', width: 80, height: 80 }}>
      <svg width="80" height="80" viewBox="0 0 80 80" aria-label={`CPU usage ${percent.toFixed(1)}%`}>
        {/* Background track */}
        <circle
          cx="40"
          cy="40"
          r={normalised}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
        />
        {/* Progress arc */}
        <circle
          cx="40"
          cy="40"
          r={normalised}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 40 40)"
          style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.3s ease' }}
        />
      </svg>
      {/* Centre label */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
            fontWeight: 600,
            color,
            lineHeight: 1,
          }}
        >
          {percent.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

/** Horizontal bar for RAM usage */
function RamBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  const color =
    pct > 85
      ? 'var(--accent-danger)'
      : pct > 65
        ? 'var(--accent-warning)'
        : 'var(--accent-success)';

  return (
    <div style={{ width: '100%' }}>
      <div
        style={{
          height: 6,
          background: 'rgba(255,255,255,0.06)',
          borderRadius: 3,
          overflow: 'hidden',
          marginBottom: 4,
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: color,
            borderRadius: 3,
            boxShadow: `0 0 8px ${color}60`,
            transition: 'width 0.6s ease, background 0.3s ease',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.68rem',
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <span>{used.toFixed(1)} GB used</span>
        <span>{total.toFixed(1)} GB total</span>
      </div>
    </div>
  );
}

/** Single glassmorphism metric card */
function MetricCard({
  icon,
  label,
  children,
  accent = 'var(--accent-primary)',
}: {
  icon: string;
  label: string;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <div
      style={{
        background: 'rgba(26, 35, 50, 0.65)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14,
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = `${accent}40`;
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 4px 24px rgba(0,0,0,0.35), 0 0 20px ${accent}18`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.06)';
        (e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 24px rgba(0,0,0,0.35)';
      }}
    >
      {/* Top accent line */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(90deg, transparent, ${accent}60, transparent)`,
        }}
      />
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ fontSize: '1.1rem' }}>{icon}</span>
        <span
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '0.72rem',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
          }}
        >
          {label}
        </span>
      </div>
      {children}
    </div>
  );
}

/** Large numeric display */
function BigNumber({
  value,
  unit,
  color = 'var(--text-primary)',
}: {
  value: string;
  unit?: string;
  color?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '2rem',
          fontWeight: 700,
          color,
          lineHeight: 1,
          letterSpacing: '-0.03em',
          transition: 'color 0.3s ease',
        }}
      >
        {value}
      </span>
      {unit && (
        <span
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            fontWeight: 500,
          }}
        >
          {unit}
        </span>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function MetricsPanel({ wsMetrics, wsConnected }: MetricsPanelProps) {
  const [metrics, setMetrics] = useState<MetricsData>({
    cpu_percent: 0,
    ram_used_gb: 0,
    ram_total_gb: 16,
    faiss_vectors: 0,
    atlas_docs: 0,
    daemon_uptime_seconds: 0,
    query_count: 0,
    avg_latency_ms: 0,
  });

  // Live uptime ticker
  const uptimeRef = useRef(0);
  useEffect(() => {
    const ticker = setInterval(() => {
      setMetrics((prev) => ({
        ...prev,
        daemon_uptime_seconds: prev.daemon_uptime_seconds + 1,
      }));
    }, 1000);
    return () => clearInterval(ticker);
  }, []);

  // Apply WebSocket metrics when they arrive
  useEffect(() => {
    if (wsMetrics) {
      uptimeRef.current = wsMetrics.daemon_uptime_seconds;
      setMetrics(wsMetrics);
    }
  }, [wsMetrics]);

  // Fallback polling when WebSocket is not connected
  const fetchMetrics = useCallback(async () => {
    try {
      const { data } = await axios.get<MetricsData>('/api/metrics');
      setMetrics(data);
    } catch {
      // Silently ignore — we keep showing last known values
    }
  }, []);

  useEffect(() => {
    if (!wsConnected) {
      void fetchMetrics();
      const interval = setInterval(() => void fetchMetrics(), POLL_INTERVAL_MS);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [wsConnected, fetchMetrics]);

  return (
    <div>
      {/* Section header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <h2
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '0.95rem',
            fontWeight: 600,
            color: 'var(--text-primary)',
            letterSpacing: '-0.01em',
          }}
        >
          System Metrics
        </h2>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: '0.7rem',
            color: wsConnected ? 'var(--accent-success)' : 'var(--accent-warning)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'currentColor',
              display: 'inline-block',
              animation: wsConnected ? 'pulse-dot 2s infinite' : 'none',
            }}
          />
          {wsConnected ? 'Live (WebSocket)' : 'Polling (15s)'}
        </div>
      </div>

      {/* Metrics grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: 16,
        }}
      >
        {/* CPU */}
        <MetricCard icon="⚡" label="CPU Usage" accent="var(--accent-primary)">
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <CpuRing percent={metrics.cpu_percent} />
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>
                Utilisation
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {metrics.cpu_percent.toFixed(1)}%
              </div>
            </div>
          </div>
        </MetricCard>

        {/* RAM */}
        <MetricCard icon="🧠" label="Memory" accent="var(--accent-success)">
          <BigNumber
            value={metrics.ram_used_gb.toFixed(1)}
            unit="GB"
            color="var(--accent-success)"
          />
          <RamBar used={metrics.ram_used_gb} total={metrics.ram_total_gb} />
        </MetricCard>

        {/* FAISS Vectors */}
        <MetricCard icon="🔷" label="FAISS Vectors" accent="var(--accent-primary)">
          <BigNumber
            value={formatNumber(metrics.faiss_vectors)}
            unit="vectors"
            color="var(--accent-primary)"
          />
          <div
            style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
          >
            {metrics.faiss_vectors.toLocaleString()} indexed
          </div>
        </MetricCard>

        {/* Atlas Docs */}
        <MetricCard icon="📚" label="Atlas Docs" accent="var(--accent-success)">
          <BigNumber
            value={formatNumber(metrics.atlas_docs)}
            unit="documents"
            color="var(--accent-success)"
          />
          <div
            style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
          >
            {metrics.atlas_docs.toLocaleString()} stored
          </div>
        </MetricCard>

        {/* Daemon Uptime */}
        <MetricCard icon="🕐" label="Daemon Uptime" accent="var(--accent-purple)">
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '1.8rem',
              fontWeight: 700,
              color: 'var(--accent-purple)',
              letterSpacing: '0.04em',
              lineHeight: 1,
            }}
          >
            {formatUptime(metrics.daemon_uptime_seconds)}
          </div>
          <div
            style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}
          >
            HH:MM:SS
          </div>
        </MetricCard>

        {/* Avg Latency */}
        <MetricCard icon="⏱️" label="Avg Latency" accent="var(--accent-warning)">
          <BigNumber
            value={metrics.avg_latency_ms != null ? metrics.avg_latency_ms.toFixed(0) : '—'}
            unit="ms"
            color="var(--accent-warning)"
          />
          <div
            style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}
          >
            {metrics.query_count ?? 0} queries total
          </div>
        </MetricCard>
      </div>
    </div>
  );
}
