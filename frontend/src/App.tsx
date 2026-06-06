import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './hooks/useAuth';
import { useWebSocket } from './hooks/useWebSocket';
import { ServiceHealthBar } from './components/ServiceHealthBar';
import { QueryForm } from './components/QueryForm';
import { ReasoningTrace } from './components/ReasoningTrace';
import { RAGViewer, RagChunk } from './components/RAGViewer';
import { MetricsPanel, MetricsData } from './components/MetricsPanel';
import { AuditLog } from './components/AuditLog';

// ─── Login Component ──────────────────────────────────────────────────────────

function LoginPanel() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } }; message?: string };
      setError(e.response?.data?.error ?? e.message ?? 'Login failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
        fontFamily: 'var(--font-sans)',
        padding: 20,
      }}
    >
      <form
        onSubmit={(e) => void handleSubmit(e)}
        style={{
          background: 'rgba(26, 35, 50, 0.65)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 16,
          padding: 32,
          width: '100%',
          maxWidth: 400,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 3,
            background: 'linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))',
            borderTopLeftRadius: 16,
            borderTopRightRadius: 16,
          }}
        />

        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div
            style={{
              width: 48,
              height: 48,
              background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              borderRadius: 10,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.1rem',
              fontWeight: 800,
              color: '#fff',
              marginBottom: 12,
              boxShadow: '0 0 16px rgba(59, 130, 246, 0.4)',
            }}
          >
            AI
          </div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            AIOS Middleware Login
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 6 }}>
            B.Tech Capstone Project
          </p>
        </div>

        {error && (
          <div className="alert-error" style={{ marginBottom: 20 }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: 18 }}>
          <label
            htmlFor="email"
            style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}
          >
            OPERATOR EMAIL
          </label>
          <input
            id="email"
            type="email"
            placeholder="operator@aios"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading}
            required
            style={{
              width: '100%',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 8,
              padding: '10px 12px',
              color: 'var(--text-primary)',
              outline: 'none',
              fontSize: '0.85rem',
              boxSizing: 'border-box',
            }}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label
            htmlFor="password"
            style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}
          >
            PASSWORD
          </label>
          <input
            id="password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
            required
            style={{
              width: '100%',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 8,
              padding: '10px 12px',
              color: 'var(--text-primary)',
              outline: 'none',
              fontSize: '0.85rem',
              boxSizing: 'border-box',
            }}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading}
          style={{ width: '100%', padding: '11px', fontWeight: 600 }}
        >
          {loading ? 'Authenticating...' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}

// ─── Dashboard Component ──────────────────────────────────────────────────────

function DashboardContent() {
  const { user, logout } = useAuth();
  const [streamingTokens, setStreamingTokens] = useState('');
  const [intent, setIntent] = useState<Record<string, unknown> | null>(null);
  const [validationStatus, setValidationStatus] = useState<string | null>(null);
  const [validationIntentId, setValidationIntentId] = useState<number | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [ragChunks, setRagChunks] = useState<RagChunk[]>([]);
  const [wsMetrics, setWsMetrics] = useState<MetricsData | undefined>(undefined);
  const [isStreaming, setIsStreaming] = useState(false);

  // Setup live WebSocket handlers
  const { connected } = useWebSocket('/stream', {
    token: (data) => {
      if (data.token && typeof data.token === 'string') {
        setStreamingTokens((prev) => prev + data.token);
      }
    },
    stream_done: (data) => {
      if (typeof data.latency_ms === 'number') {
        setLatencyMs(data.latency_ms);
        setIsStreaming(false);
      }
    },
    intent_parsed: (data) => {
      if (data.intent && typeof data.intent === 'object') {
        setIntent(data.intent as Record<string, unknown>);
      }
    },
    validation_result: (data) => {
      if (typeof data.result === 'string') {
        setValidationStatus(data.result);
      }
      if (typeof data.intent_id === 'number') {
        setValidationIntentId(data.intent_id);
      }
    },
    rag_retrieved: (data) => {
      if (Array.isArray(data.chunks)) {
        setRagChunks(data.chunks as RagChunk[]);
      }
    },
    metrics_update: (data) => {
      const metricsPayload = data.metrics ? data.metrics : data;
      const { type: _, ...metrics } = metricsPayload as Record<string, unknown>;
      setWsMetrics(metrics as unknown as MetricsData);
    },
  });

  const handleQueryId = (_id: string) => {
    setStreamingTokens('');
    setIntent(null);
    setValidationStatus(null);
    setValidationIntentId(null);
    setLatencyMs(null);
    setRagChunks([]);
  };

  const handleApprove = (_intentId: number) => {
    setValidationStatus('APPROVED');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--bg-primary)',
        color: 'var(--text-primary)',
        paddingTop: 68, // Account for fixed ServiceHealthBar
        paddingBottom: 40,
        boxSizing: 'border-box',
      }}
    >
      {/* Top Health Status Bar */}
      <ServiceHealthBar />

      {/* Header / Nav */}
      <header
        style={{
          maxWidth: 1400,
          margin: '0 auto 24px',
          padding: '0 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
            AI-Native Operating System Control Panel
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
            Telemetry Monitoring, Real-time RAG Context & Control Plane Decision Gate
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* WS status */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: '0.72rem',
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: connected ? 'var(--accent-success)' : 'var(--accent-danger)',
                boxShadow: connected ? '0 0 6px var(--accent-success)' : 'none',
              }}
            />
            <span style={{ color: 'var(--text-secondary)' }}>
              {connected ? 'WS CONNECTED' : 'WS DISCONNECTED'}
            </span>
          </div>

          {/* User info */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              padding: '6px 12px',
              borderRadius: 8,
              fontSize: '0.72rem',
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>OPERATOR:</span>
            <span style={{ fontWeight: 600 }}>{user?.sub}</span>
            <span className="badge badge-info" style={{ fontSize: '0.62rem', padding: '1px 6px' }}>
              {user?.role}
            </span>
          </div>

          <button
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.72rem' }}
            onClick={logout}
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <main
        style={{
          maxWidth: 1400,
          margin: '0 auto',
          padding: '0 20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(600px, 1fr))',
          gap: 24,
          boxSizing: 'border-box',
        }}
      >
        {/* Left Column: Interactivity */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <QueryForm
            onQueryId={(id) => {
              handleQueryId(id);
              setIsStreaming(true);
            }}
            onTokenReceived={(tok) => setStreamingTokens((p) => p + tok)}
            isStreaming={isStreaming}
            setIsStreaming={setIsStreaming}
          />
          <ReasoningTrace
            streamingTokens={streamingTokens}
            intent={intent}
            validationStatus={validationStatus}
            validationIntentId={validationIntentId}
            latencyMs={latencyMs}
            onApprove={handleApprove}
          />
          <RAGViewer chunks={ragChunks} />
        </div>

        {/* Right Column: Dashboards / Auditing */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <MetricsPanel wsMetrics={wsMetrics} wsConnected={connected} />
          <AuditLog />
        </div>
      </main>
    </div>
  );
}

// ─── Auth Gate wrapper ────────────────────────────────────────────────────────

function AuthGate() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <DashboardContent /> : <LoginPanel />;
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
