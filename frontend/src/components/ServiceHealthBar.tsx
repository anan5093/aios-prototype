import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';

// ─── Types ────────────────────────────────────────────────────────────────────

type ServiceStatus = 'healthy' | 'down' | 'unknown';

interface ServiceHealth {
  name: string;
  status: ServiceStatus;
  latencyMs?: number;
}

interface HealthApiResponse {
  services?: Record<string, string | boolean | Record<string, unknown>>;
  status?: string;
  [key: string]: unknown;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SERVICE_KEYS: Array<{ key: string; label: string }> = [
  { key: 'faiss', label: 'FAISS' },
  { key: 'atlas', label: 'Atlas' },
  { key: 'colab_tunnel', label: 'Colab Tunnel' },
  { key: 'local_ollama', label: 'Local Ollama' },
  { key: 'daemon', label: 'Daemon' },
];

const POLL_INTERVAL_MS = 10_000;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function parseStatus(raw: unknown): ServiceStatus {
  if (raw === true || raw === 'healthy' || raw === 'ok' || raw === 'up') return 'healthy';
  if (raw === false || raw === 'down' || raw === 'error' || raw === 'unavailable') return 'down';
  return 'unknown';
}

function buildServices(data: HealthApiResponse): ServiceHealth[] {
  const src = data.services ?? data;
  return SERVICE_KEYS.map(({ key, label }) => ({
    name: label,
    status: parseStatus((src as Record<string, unknown>)[key] ?? data[key]),
  }));
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface StatusDotProps {
  status: ServiceStatus;
}

function StatusDot({ status }: StatusDotProps) {
  const color =
    status === 'healthy'
      ? 'var(--accent-success)'
      : status === 'down'
        ? 'var(--accent-danger)'
        : 'var(--accent-warning)';

  const pulsing = status === 'healthy';

  return (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: color,
        boxShadow: pulsing ? `0 0 6px ${color}` : 'none',
        animation: pulsing ? 'pulse-dot 2s ease-in-out infinite' : 'none',
        flexShrink: 0,
      }}
    />
  );
}

interface ServicePillProps {
  service: ServiceHealth;
}

function ServicePill({ service }: ServicePillProps) {
  const statusLabel =
    service.status === 'healthy' ? 'OK' : service.status === 'down' ? 'DOWN' : '—';
  const statusColor =
    service.status === 'healthy'
      ? 'var(--accent-success)'
      : service.status === 'down'
        ? 'var(--accent-danger)'
        : 'var(--accent-warning)';

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 10px',
        borderRadius: 9999,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.07)',
        cursor: 'default',
        userSelect: 'none',
      }}
    >
      <StatusDot status={service.status} />
      <span
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '0.72rem',
          fontWeight: 500,
          color: 'var(--text-secondary)',
          letterSpacing: '0.02em',
        }}
      >
        {service.name}
      </span>
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.65rem',
          fontWeight: 600,
          color: statusColor,
          letterSpacing: '0.05em',
        }}
      >
        {statusLabel}
      </span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function ServiceHealthBar() {
  const [services, setServices] = useState<ServiceHealth[]>(
    SERVICE_KEYS.map(({ label }) => ({ name: label, status: 'unknown' as ServiceStatus })),
  );
  const [currentTime, setCurrentTime] = useState<string>(formatTime(new Date()));
  const [lastFetched, setLastFetched] = useState<string>('—');
  const [overallStatus, setOverallStatus] = useState<'operational' | 'degraded' | 'outage'>(
    'operational',
  );

  const fetchHealth = useCallback(async () => {
    try {
      const { data } = await axios.get<HealthApiResponse>('/api/health');
      const parsed = buildServices(data);
      setServices(parsed);
      setLastFetched(formatTime(new Date()));

      const downCount = parsed.filter((s) => s.status === 'down').length;
      const unknownCount = parsed.filter((s) => s.status === 'unknown').length;
      if (downCount > 1) setOverallStatus('outage');
      else if (downCount > 0 || unknownCount > 1) setOverallStatus('degraded');
      else setOverallStatus('operational');
    } catch {
      // On network error, mark all as unknown but don't crash
      setServices((prev) => prev.map((s) => ({ ...s, status: 'unknown' as ServiceStatus })));
      setOverallStatus('degraded');
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    void fetchHealth();
    const interval = setInterval(() => void fetchHealth(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  // Live clock
  useEffect(() => {
    const clockInterval = setInterval(() => {
      setCurrentTime(formatTime(new Date()));
    }, 1000);
    return () => clearInterval(clockInterval);
  }, []);

  const overallColor =
    overallStatus === 'operational'
      ? 'var(--accent-success)'
      : overallStatus === 'degraded'
        ? 'var(--accent-warning)'
        : 'var(--accent-danger)';

  const overallLabel =
    overallStatus === 'operational'
      ? 'All Systems Operational'
      : overallStatus === 'degraded'
        ? 'Degraded Performance'
        : 'System Outage';

  return (
    <div
      role="banner"
      aria-label="Service health status bar"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: 48,
        background: '#0d1117',
        borderBottom: '1px solid rgba(59, 130, 246, 0.15)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        zIndex: 1000,
        gap: 16,
        boxShadow: '0 1px 0 rgba(59, 130, 246, 0.08), 0 2px 16px rgba(0,0,0,0.4)',
      }}
    >
      {/* Left: AIOS brand mark */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.65rem',
            fontWeight: 800,
            color: '#fff',
            letterSpacing: '-0.02em',
            fontFamily: 'var(--font-sans)',
            boxShadow: '0 0 12px rgba(59, 130, 246, 0.4)',
          }}
        >
          AI
        </div>
        <span
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '0.8rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            letterSpacing: '0.04em',
          }}
        >
          AIOS
        </span>
      </div>

      {/* Center: Service pills */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flex: 1,
          justifyContent: 'center',
          flexWrap: 'nowrap',
          overflow: 'hidden',
        }}
      >
        {services.map((svc) => (
          <ServicePill key={svc.name} service={svc} />
        ))}
      </div>

      {/* Right: Overall status + time */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexShrink: 0,
        }}
      >
        {/* Overall indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <span style={{ fontSize: 7, color: overallColor }}>●</span>
          <span
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '0.68rem',
              fontWeight: 500,
              color: overallColor,
              letterSpacing: '0.03em',
            }}
          >
            {overallLabel}
          </span>
        </div>

        {/* Divider */}
        <div
          style={{
            width: 1,
            height: 20,
            background: 'rgba(255,255,255,0.08)',
          }}
        />

        {/* Time */}
        <div style={{ textAlign: 'right' }}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.78rem',
              fontWeight: 500,
              color: 'var(--text-primary)',
              letterSpacing: '0.08em',
            }}
          >
            {currentTime}
          </div>
          <div
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '0.6rem',
              color: 'var(--text-muted)',
              letterSpacing: '0.04em',
            }}
          >
            Last sync: {lastFetched}
          </div>
        </div>
      </div>
    </div>
  );
}
