import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../hooks/useAuth';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuditIntentRecord {
  id: number;
  created_at: string;
  intent_json: string;
  action_type: string;
  confidence_score: number;
  validation_result: string;
  rejection_reason: string | null;
  execution_status: string;
  approved_by: string | null;
  approved_at: string | null;
  record_hash: string;
}

interface IntentsResponse {
  total: number;
  page: number;
  intents: AuditIntentRecord[];
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function AuditLog() {
  const { hasRole, user } = useAuth();
  const [intents, setIntents] = useState<AuditIntentRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [approvingId, setApprovingId] = useState<number | null>(null);

  const fetchIntents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get<IntentsResponse>(
        `/api/intents?page=${page}&limit=${limit}`
      );
      setIntents(response.data.intents);
      setTotal(response.data.total);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } }; message?: string };
      setError(e.response?.data?.error ?? e.message ?? 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page, limit]);

  useEffect(() => {
    void fetchIntents();
  }, [fetchIntents]);

  const handleApprove = async (id: number) => {
    setApprovingId(id);
    try {
      await axios.put(`/api/intents/${id}/approve`, {
        approved_by: user?.sub ?? 'operator@aios',
      });
      // Refresh list
      await fetchIntents();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string } }; message?: string };
      alert(e.response?.data?.message ?? e.message ?? 'Approval failed');
    } finally {
      setApprovingId(null);
    }
  };

  const totalPages = Math.ceil(total / limit);

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
        fontFamily: 'var(--font-sans)',
      }}
    >
      <h2
        style={{
          fontSize: '0.95rem',
          fontWeight: 600,
          color: 'var(--text-primary)',
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ color: 'var(--accent-success)' }}>◼</span>
        Control Plane Audit Log
      </h2>

      {error && (
        <div className="alert-danger" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      {loading && intents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-secondary)' }}>
          Loading audit records...
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.82rem',
              textAlign: 'left',
              color: 'var(--text-secondary)',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <th style={{ padding: '10px 8px' }}>ID</th>
                <th style={{ padding: '10px 8px' }}>Timestamp</th>
                <th style={{ padding: '10px 8px' }}>Action Type</th>
                <th style={{ padding: '10px 8px' }}>Confidence</th>
                <th style={{ padding: '10px 8px' }}>Validation</th>
                <th style={{ padding: '10px 8px' }}>Execution</th>
                <th style={{ padding: '10px 8px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {intents.map((record) => {
                const isExpanded = expandedId === record.id;
                const isPendingApprove =
                  record.validation_result === 'VALIDATED' &&
                  record.execution_status === 'PENDING';

                return (
                  <React.Fragment key={record.id}>
                    <tr
                      onClick={() => setExpandedId(isExpanded ? null : record.id)}
                      style={{
                        borderBottom: '1px solid rgba(255,255,255,0.05)',
                        cursor: 'pointer',
                        background: isExpanded ? 'rgba(255,255,255,0.02)' : 'transparent',
                      }}
                      className="audit-row"
                    >
                      <td style={{ padding: '12px 8px', fontFamily: 'var(--font-mono)' }}>
                        #{record.id}
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        {new Date(record.created_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '12px 8px', fontWeight: 600 }}>
                        {record.action_type}
                      </td>
                      <td style={{ padding: '12px 8px', fontFamily: 'var(--font-mono)' }}>
                        {(record.confidence_score * 100).toFixed(1)}%
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        <span
                          className={`badge badge-${
                            record.validation_result === 'VALIDATED'
                              ? 'success'
                              : record.validation_result === 'PENDING_REVIEW'
                                ? 'warning'
                                : 'danger'
                          }`}
                        >
                          {record.validation_result}
                        </span>
                      </td>
                      <td style={{ padding: '12px 8px' }}>
                        <span
                          className={`badge badge-${
                            record.execution_status === 'SIMULATED_EXECUTED'
                              ? 'success'
                              : 'info'
                          }`}
                        >
                          {record.execution_status}
                        </span>
                      </td>
                      <td
                        style={{ padding: '12px 8px' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {isPendingApprove && hasRole('operator') ? (
                          <button
                            className="btn btn-success"
                            style={{ padding: '3px 8px', fontSize: '0.7rem' }}
                            onClick={() => void handleApprove(record.id)}
                            disabled={approvingId === record.id}
                          >
                            {approvingId === record.id ? '...' : 'Approve'}
                          </button>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr style={{ background: '#0a0e1a' }}>
                        <td colSpan={7} style={{ padding: 16 }}>
                          <div style={{ marginBottom: 12 }}>
                            <strong style={{ color: 'var(--text-primary)' }}>Audit Record Hash:</strong>
                            <pre
                              style={{
                                margin: '4px 0 0 0',
                                fontFamily: 'var(--font-mono)',
                                fontSize: '0.72rem',
                                color: 'var(--accent-purple)',
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-wrap',
                              }}
                            >
                              {record.record_hash}
                            </pre>
                          </div>
                          {record.rejection_reason && (
                            <div style={{ marginBottom: 12 }}>
                              <strong style={{ color: 'var(--accent-danger)' }}>Rejection Reason:</strong>
                              <p style={{ margin: '4px 0 0 0', color: 'var(--text-primary)' }}>
                                {record.rejection_reason}
                              </p>
                            </div>
                          )}
                          {record.approved_by && (
                            <div style={{ marginBottom: 12, color: 'var(--text-secondary)' }}>
                              <strong>Approved By:</strong> {record.approved_by} |{' '}
                              <strong>Approved At:</strong>{' '}
                              {new Date(record.approved_at || '').toLocaleString()}
                            </div>
                          )}
                          <div>
                            <strong style={{ color: 'var(--text-primary)' }}>Intent Proposal Payload:</strong>
                            <pre
                              style={{
                                margin: '6px 0 0 0',
                                background: '#05070f',
                                border: '1px solid rgba(255,255,255,0.05)',
                                padding: 12,
                                borderRadius: 6,
                                fontFamily: 'var(--font-mono)',
                                fontSize: '0.75rem',
                                color: 'var(--text-secondary)',
                                overflowX: 'auto',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}
                            >
                              {JSON.stringify(JSON.parse(record.intent_json || '{}'), null, 2)}
                            </pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div
          style={{
            marginTop: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
          }}
        >
          <span>
            Showing page {page} of {totalPages} ({total} total records)
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
            >
              Previous
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
              disabled={page === totalPages}
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
