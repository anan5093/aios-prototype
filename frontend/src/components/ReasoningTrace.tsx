import { useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../hooks/useAuth';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ReasoningTraceProps {
  streamingTokens: string;
  intent: Record<string, unknown> | null;
  validationStatus: string | null;
  validationIntentId: number | null;
  latencyMs: number | null;
  onApprove: (intentId: number) => void;
}

type ValidationStatus = 'VALIDATED' | 'PENDING_REVIEW' | 'REJECTED' | string;

// ─── JSON Syntax Highlighter ──────────────────────────────────────────────────

function syntaxHighlightJson(obj: Record<string, unknown>): string {
  const json = JSON.stringify(obj, null, 2);
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          return `<span class="json-key">${match}</span>`;
        }
        return `<span class="json-string">${match}</span>`;
      }
      if (/true|false/.test(match)) {
        return `<span class="json-boolean">${match}</span>`;
      }
      if (/null/.test(match)) {
        return `<span class="json-null">${match}</span>`;
      }
      return `<span class="json-number">${match}</span>`;
    },
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function ValidationBadge({ status }: { status: ValidationStatus }) {
  const config: Record<string, { bg: string; color: string; border: string; icon: string; label: string }> = {
    VALIDATED: {
      bg: 'var(--accent-success-dim)',
      color: 'var(--accent-success)',
      border: 'rgba(16,185,129,0.3)',
      icon: '✓',
      label: 'VALIDATED',
    },
    PENDING_REVIEW: {
      bg: 'var(--accent-warning-dim)',
      color: 'var(--accent-warning)',
      border: 'rgba(245,158,11,0.3)',
      icon: '⏳',
      label: 'PENDING REVIEW',
    },
    REJECTED: {
      bg: 'var(--accent-danger-dim)',
      color: 'var(--accent-danger)',
      border: 'rgba(239,68,68,0.3)',
      icon: '✕',
      label: 'REJECTED',
    },
  };

  const cfg = config[status] ?? config['PENDING_REVIEW'];

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 12px',
        borderRadius: 9999,
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        color: cfg.color,
        fontFamily: 'var(--font-sans)',
        fontSize: '0.72rem',
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase' as const,
      }}
    >
      <span>{cfg.icon}</span>
      <span>{cfg.label}</span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function ReasoningTrace({
  streamingTokens,
  intent,
  validationStatus,
  validationIntentId,
  latencyMs,
  onApprove,
}: ReasoningTraceProps) {
  const { hasRole, user } = useAuth();
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  const isStreaming = streamingTokens.length > 0 && latencyMs === null;
  const isDone = latencyMs !== null;
  const hasContent = streamingTokens.length > 0 || intent !== null;

  const canApprove =
    hasRole('operator') &&
    validationStatus === 'VALIDATED' &&
    validationIntentId !== null &&
    !approved;

  const handleApprove = useCallback(async () => {
    if (validationIntentId === null) return;
    setApproving(true);
    setApproveError(null);
    try {
      await axios.put(`/api/intents/${validationIntentId}/approve`, {
        approved_by: user?.sub ?? 'operator@aios',
      });
      setApproved(true);
      onApprove(validationIntentId);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setApproveError(e.response?.data?.detail ?? e.message ?? 'Approval failed');
    } finally {
      setApproving(false);
    }
  }, [validationIntentId, user, onApprove]);

  if (!hasContent) {
    return (
      <div
        style={{
          background: 'rgba(26,35,50,0.65)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14,
          padding: 24,
          boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
        }}
      >
        <h2
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '0.95rem',
            fontWeight: 600,
            color: 'var(--text-primary)',
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ color: 'var(--accent-primary)' }}>◎</span>
          Reasoning Trace
        </h2>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 100,
            color: 'var(--text-muted)',
            fontSize: '0.85rem',
            fontFamily: 'var(--font-sans)',
            gap: 8,
          }}
        >
          <span style={{ fontSize: '2rem', opacity: 0.3 }}>◎</span>
          <span>Submit a query to see the AI reasoning trace</span>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'rgba(26,35,50,0.65)',
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
          background: 'linear-gradient(90deg, transparent, var(--accent-purple)80, transparent)',
        }}
      />

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 10,
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
          <span style={{ color: 'var(--accent-purple)' }}>◎</span>
          Reasoning Trace
          {isStreaming && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: '0.65rem',
                color: 'var(--accent-warning)',
                fontWeight: 500,
                fontFamily: 'var(--font-sans)',
              }}
            >
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: 'var(--accent-warning)',
                  display: 'inline-block',
                  animation: 'pulse-dot 1s infinite',
                }}
              />
              LIVE
            </span>
          )}
        </h2>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {validationStatus && <ValidationBadge status={validationStatus} />}
          {isDone && latencyMs !== null && (
            <span
              style={{
                fontSize: '0.72rem',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              Completed in {latencyMs}ms
            </span>
          )}
        </div>
      </div>

      {/* Token stream — shown while streaming or can be toggled */}
      {(isStreaming || (isDone && showRaw)) && (
        <div
          style={{
            background: '#0a0e1a',
            border: '1px solid rgba(59,130,246,0.15)',
            borderRadius: 10,
            padding: '14px 16px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            color: '#c9d1d9',
            lineHeight: 1.7,
            maxHeight: 280,
            overflowY: 'auto',
            marginBottom: 16,
            wordBreak: 'break-word',
            whiteSpace: 'pre-wrap',
          }}
        >
          {streamingTokens}
          {isStreaming && (
            <span
              style={{
                display: 'inline-block',
                width: 2,
                height: '1em',
                background: 'var(--accent-primary)',
                marginLeft: 1,
                verticalAlign: 'text-bottom',
                animation: 'blink-cursor 1s step-end infinite',
              }}
            />
          )}
        </div>
      )}

      {/* Structured intent — shown after stream completes */}
      {isDone && intent !== null && (
        <div>
          {/* Toggle raw stream */}
          {streamingTokens && (
            <button
              onClick={() => setShowRaw((v) => !v)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-primary)',
                fontSize: '0.75rem',
                cursor: 'pointer',
                padding: '0 0 12px 0',
                fontFamily: 'var(--font-sans)',
                textDecoration: 'underline',
              }}
            >
              {showRaw ? 'Hide' : 'Show'} raw token stream
            </button>
          )}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 10,
            }}
          >
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-sans)',
              }}
            >
              Parsed Intent
            </span>
          </div>

          <pre
            dangerouslySetInnerHTML={{ __html: syntaxHighlightJson(intent) }}
            style={{
              background: '#060a12',
              border: '1px solid rgba(59,130,246,0.12)',
              borderRadius: 10,
              padding: '14px 16px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.78rem',
              lineHeight: 1.65,
              overflowX: 'auto',
              margin: 0,
              marginBottom: 16,
              color: 'var(--text-secondary)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          />

          {/* Approve action */}
          {canApprove && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <button
                className="btn btn-success"
                onClick={() => void handleApprove()}
                disabled={approving}
              >
                {approving ? (
                  <>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 13,
                        height: 13,
                        border: '2px solid rgba(255,255,255,0.3)',
                        borderTopColor: '#fff',
                        borderRadius: '50%',
                        animation: 'spin 0.65s linear infinite',
                      }}
                    />
                    Approving…
                  </>
                ) : (
                  <>✓ Approve Intent</>
                )}
              </button>
              {approveError && (
                <span
                  style={{
                    fontSize: '0.78rem',
                    color: 'var(--accent-danger)',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  {approveError}
                </span>
              )}
            </div>
          )}

          {approved && (
            <div className="alert-info" style={{ marginTop: 8 }}>
              ✓ Intent #{validationIntentId} approved and queued for simulated execution.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
