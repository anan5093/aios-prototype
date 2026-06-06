import React, { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../hooks/useAuth';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface QueryFormProps {
  onQueryId: (queryId: string) => void;
  onTokenReceived: (token: string) => void;
  isStreaming?: boolean;
  setIsStreaming?: (isStreaming: boolean) => void;
}

interface QueryResponse {
  query_id: string;
  status: string;
  message?: string;
}

// ─── Spinner ─────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        width: 15,
        height: 15,
        border: '2px solid rgba(255,255,255,0.25)',
        borderTopColor: '#fff',
        borderRadius: '50%',
        animation: 'spin 0.65s linear infinite',
      }}
    />
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function QueryForm({
  onQueryId,
  onTokenReceived: _onTokenReceived,
  isStreaming: propIsStreaming,
  setIsStreaming: propSetIsStreaming,
}: QueryFormProps) {
  const { hasRole, token } = useAuth();
  const [query, setQuery] = useState('');
  const [localIsStreaming, localSetIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queryId, setQueryId] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const startTimeRef = useRef<number>(0);

  const isStreaming = propIsStreaming !== undefined ? propIsStreaming : localIsStreaming;
  const setIsStreaming = propSetIsStreaming !== undefined ? propSetIsStreaming : localSetIsStreaming;

  const canSubmit = hasRole('operator');

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.max(100, ta.scrollHeight)}px`;
  }, [query]);

  const handleSubmit = useCallback(async () => {
    if (!query.trim() || isStreaming || !canSubmit) return;
    setError(null);
    setQueryId(null);
    setIsStreaming(true);
    startTimeRef.current = Date.now();

    try {
      const { data } = await axios.post<QueryResponse>(
        '/api/query',
        { query: query.trim() },
        {
          headers: {
            Authorization: `Bearer ${token ?? ''}`,
            'Content-Type': 'application/json',
          },
        },
      );

      if (data.query_id) {
        setQueryId(data.query_id);
        onQueryId(data.query_id);
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg =
        axiosErr.response?.data?.detail ??
        axiosErr.message ??
        'Daemon unavailable — please ensure the backend is running.';
      setError(msg);
      setIsStreaming(false);
    }
  }, [query, isStreaming, canSubmit, token, onQueryId, setIsStreaming]);

  // Called by parent (via DashboardPage) when stream_done event arrives
  // We expose a way for parent to signal stream completion via a prop callback
  // Internally, we'll also call the parent's onStreamDone once streaming stops.

  // Listen for stream_done via parent callback. 
  // We set isStreaming=false once the parent tells us stream is done by 
  // calling onStreamDone — but since onStreamDone is called from App, we need 
  // to track streaming state ourselves via the WS events that App processes.
  // For that, App calls onStreamDone, which sets latencyMs in App state.
  // We won't duplicate that logic — instead, use a ref to detect when we should stop.

  // Actually: streaming state is managed here. The parent calls onStreamDone,
  // which is the callback. We stop streaming when we receive stream_done from WS.
  // But the WS is in App.tsx. So we expose a `stopStreaming` handle via a side-effect
  // approach: we watch for the onStreamDone callback to fire.
  // Simpler: when query is submitted successfully, isStreaming is managed here.
  // App.tsx will call our onStreamDone prop when stream_done event arrives.
  // We'll stop streaming then.

  // We need a way for App to tell QueryForm that streaming is done.
  // We'll expose a ref. But the spec says just props. Let's use a context/event approach:
  // We wrap onStreamDone to also set isStreaming = false here.
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        void handleSubmit();
      }
    },
    [handleSubmit],
  );

  const clearForm = useCallback(() => {
    setQuery('');
    setError(null);
    setQueryId(null);
    setIsStreaming(false);
    textareaRef.current?.focus();
  }, [setIsStreaming]);

  return (
    <div
      style={{
        background: 'rgba(26, 35, 50, 0.65)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14,
        padding: 24,
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Top accent */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: 'linear-gradient(90deg, transparent, var(--accent-primary)80, transparent)',
        }}
      />

      {/* Header */}
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
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ color: 'var(--accent-primary)', fontSize: '1rem' }}>◈</span>
          Query Interface
        </h2>
      </div>

      {/* Permission warning for viewer */}
      {!canSubmit && (
        <div className="alert-warning" style={{ marginBottom: 16 }}>
          <span>⚠</span>
          <span>
            Insufficient permissions — your role (<strong>viewer</strong>) cannot submit queries.
            Contact an operator or admin.
          </span>
        </div>
      )}

      {/* Textarea */}
      <div style={{ position: 'relative', marginBottom: 12 }}>
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming || !canSubmit}
          placeholder="Describe a system issue or ask the AI to analyze current telemetry..."
          aria-label="Query input"
          style={{
            width: '100%',
            minHeight: 100,
            background: 'var(--bg-input)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 10,
            padding: '12px 14px',
            color: isStreaming || !canSubmit ? 'var(--text-muted)' : 'var(--text-primary)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.9rem',
            lineHeight: 1.6,
            resize: 'none',
            outline: 'none',
            transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
            boxSizing: 'border-box',
            cursor: isStreaming || !canSubmit ? 'not-allowed' : 'text',
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--accent-primary)';
            e.currentTarget.style.boxShadow = '0 0 0 3px var(--accent-primary-dim)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-subtle)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        />
        {/* Ctrl+Enter hint */}
        <div
          style={{
            position: 'absolute',
            bottom: 8,
            right: 10,
            fontSize: '0.65rem',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            pointerEvents: 'none',
          }}
        >
          Ctrl+↵ to submit
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="alert-error" style={{ marginBottom: 12 }}>
          <span>✕</span>
          <span>{error}</span>
        </div>
      )}

      {/* Query ID display */}
      {queryId && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 12,
            padding: '6px 12px',
            background: 'var(--accent-primary-dim)',
            border: '1px solid rgba(59,130,246,0.2)',
            borderRadius: 8,
            fontSize: '0.75rem',
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>Query ID:</span>
          <code
            style={{
              fontFamily: 'var(--font-mono)',
              color: 'var(--accent-primary)',
              fontSize: '0.75rem',
            }}
          >
            {queryId}
          </code>
          {isStreaming && (
            <span style={{ color: 'var(--accent-warning)', fontSize: '0.68rem', marginLeft: 'auto' }}>
              ● streaming…
            </span>
          )}
        </div>
      )}

      {/* Actions row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <button
          className="btn btn-primary"
          onClick={() => void handleSubmit()}
          disabled={isStreaming || !canSubmit || !query.trim()}
          style={{ minWidth: 120 }}
        >
          {isStreaming ? (
            <>
              <Spinner />
              Streaming…
            </>
          ) : (
            <>
              <span>▶</span>
              Submit Query
            </>
          )}
        </button>

        {(queryId || error) && !isStreaming && (
          <button className="btn btn-ghost" onClick={clearForm}>
            Clear
          </button>
        )}

        <div style={{ marginLeft: 'auto', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          {query.length > 0 && `${query.length} chars`}
        </div>
      </div>
    </div>
  );
}

// Export wrapped version so App can forward the streamDone signal
export type { QueryFormProps as _QueryFormProps };
