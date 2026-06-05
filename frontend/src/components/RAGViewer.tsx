import { useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface RagChunk {
  chunk_id: string;
  source_file: string;
  timestamp: string;
  log_level: string;
  content: string;
  score: number;
  source_store: string;
}

export interface RAGViewerProps {
  chunks: RagChunk[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getRelativeTime(isoTimestamp: string): string {
  try {
    const date = new Date(isoTimestamp);
    const now = Date.now();
    const diffMs = now - date.getTime();
    if (isNaN(diffMs)) return isoTimestamp;
    const diffSecs = Math.floor(diffMs / 1000);
    if (diffSecs < 60) return `${diffSecs}s ago`;
    const diffMins = Math.floor(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return isoTimestamp;
  }
}

function getLogLevelStyle(level: string): { bg: string; color: string; border: string } {
  switch (level.toUpperCase()) {
    case 'ERROR':
    case 'CRITICAL':
      return {
        bg: 'var(--accent-danger-dim)',
        color: 'var(--accent-danger)',
        border: 'rgba(239,68,68,0.25)',
      };
    case 'WARN':
    case 'WARNING':
      return {
        bg: 'var(--accent-warning-dim)',
        color: 'var(--accent-warning)',
        border: 'rgba(245,158,11,0.25)',
      };
    default:
      return {
        bg: 'var(--accent-primary-dim)',
        color: 'var(--accent-primary)',
        border: 'rgba(59,130,246,0.25)',
      };
  }
}

function getSourceStoreStyle(store: string): { bg: string; color: string; border: string; label: string } {
  switch (store.toLowerCase()) {
    case 'faiss':
      return {
        bg: 'var(--accent-purple-dim)',
        color: 'var(--accent-purple)',
        border: 'rgba(139,92,246,0.25)',
        label: 'FAISS',
      };
    case 'atlas':
      return {
        bg: 'var(--accent-success-dim)',
        color: 'var(--accent-success)',
        border: 'rgba(16,185,129,0.25)',
        label: 'Atlas',
      };
    case 'both':
      return {
        bg: 'var(--accent-teal-dim)',
        color: 'var(--accent-teal)',
        border: 'rgba(20,184,166,0.25)',
        label: 'Both',
      };
    default:
      return {
        bg: 'rgba(255,255,255,0.06)',
        color: 'var(--text-muted)',
        border: 'rgba(255,255,255,0.1)',
        label: store,
      };
  }
}

function getScoreColor(score: number): string {
  if (score >= 0.8) return 'var(--accent-success)';
  if (score >= 0.5) return 'var(--accent-warning)';
  return 'var(--accent-danger)';
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface ChipProps {
  label: string;
  bg: string;
  color: string;
  border: string;
}

function Chip({ label, bg, color, border }: ChipProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: 9999,
        background: bg,
        border: `1px solid ${border}`,
        color,
        fontSize: '0.65rem',
        fontWeight: 700,
        fontFamily: 'var(--font-sans)',
        letterSpacing: '0.05em',
        textTransform: 'uppercase' as const,
        whiteSpace: 'nowrap' as const,
      }}
    >
      {label}
    </span>
  );
}

interface ScoreBarProps {
  score: number;
}

function ScoreBar({ score }: ScoreBarProps) {
  const pct = Math.min(score * 100, 100);
  const color = getScoreColor(score);
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flex: '0 0 140px',
      }}
    >
      <div
        style={{
          flex: 1,
          height: 4,
          background: 'rgba(255,255,255,0.06)',
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: color,
            borderRadius: 2,
            boxShadow: `0 0 6px ${color}80`,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.7rem',
          color,
          fontWeight: 600,
          whiteSpace: 'nowrap' as const,
          minWidth: 38,
        }}
      >
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}

// ─── Chunk Card ───────────────────────────────────────────────────────────────

function ChunkCard({ chunk, index }: { chunk: RagChunk; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const logStyle = getLogLevelStyle(chunk.log_level);
  const storeStyle = getSourceStoreStyle(chunk.source_store);
  const preview =
    chunk.content.length > 120 ? chunk.content.slice(0, 120) + '…' : chunk.content;

  return (
    <div
      style={{
        background: 'rgba(13,20,33,0.8)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 10,
        overflow: 'hidden',
        transition: 'border-color 0.2s ease',
        animation: 'fadeIn 0.25s ease both',
        animationDelay: `${index * 50}ms`,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(59,130,246,0.2)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.06)';
      }}
    >
      {/* Top row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 14px',
          borderBottom: '1px solid rgba(255,255,255,0.04)',
          flexWrap: 'wrap',
        }}
      >
        {/* Source file */}
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.72rem',
            color: 'var(--accent-primary)',
            fontWeight: 500,
            flex: 1,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={chunk.source_file}
        >
          {chunk.source_file}
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <Chip
            label={chunk.log_level.toUpperCase()}
            bg={logStyle.bg}
            color={logStyle.color}
            border={logStyle.border}
          />
          <Chip
            label={storeStyle.label}
            bg={storeStyle.bg}
            color={storeStyle.color}
            border={storeStyle.border}
          />
          <ScoreBar score={chunk.score} />
        </div>
      </div>

      {/* Content */}
      <div
        style={{
          padding: '10px 14px',
          cursor: chunk.content.length > 120 ? 'pointer' : 'default',
        }}
        onClick={() => chunk.content.length > 120 && setExpanded((v) => !v)}
      >
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)',
            lineHeight: 1.65,
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {expanded ? chunk.content : preview}
        </p>
        {chunk.content.length > 120 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent-primary)',
              fontSize: '0.72rem',
              cursor: 'pointer',
              padding: '6px 0 0 0',
              fontFamily: 'var(--font-sans)',
            }}
          >
            {expanded ? '▲ Collapse' : '▼ Expand full content'}
          </button>
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 14px 10px',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <code
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            color: 'var(--text-muted)',
          }}
        >
          {chunk.chunk_id}
        </code>
        <span
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '0.68rem',
            color: 'var(--text-muted)',
          }}
          title={chunk.timestamp}
        >
          {getRelativeTime(chunk.timestamp)}
        </span>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function RAGViewer({ chunks }: RAGViewerProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (chunks.length === 0) {
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
          <span style={{ color: 'var(--accent-purple)' }}>◈</span>
          RAG Context
          <span
            style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              fontWeight: 400,
              fontFamily: 'var(--font-sans)',
            }}
          >
            (0 chunks retrieved)
          </span>
        </h2>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 80,
            color: 'var(--text-muted)',
            fontSize: '0.85rem',
            fontFamily: 'var(--font-sans)',
            gap: 8,
          }}
        >
          <span style={{ fontSize: '1.8rem', opacity: 0.25 }}>◈</span>
          <span>No chunks retrieved yet</span>
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
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
        overflow: 'hidden',
        position: 'relative',
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
          background: 'linear-gradient(90deg, transparent, var(--accent-purple)70, var(--accent-teal)70, transparent)',
        }}
      />

      {/* Collapsible header */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '18px 24px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          borderBottom: collapsed ? 'none' : '1px solid rgba(255,255,255,0.05)',
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
            margin: 0,
          }}
        >
          <span style={{ color: 'var(--accent-purple)' }}>◈</span>
          RAG Context
          <span
            style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              fontWeight: 400,
              fontFamily: 'var(--font-sans)',
            }}
          >
            ({chunks.length} chunk{chunks.length !== 1 ? 's' : ''} retrieved)
          </span>
        </h2>
        <span
          style={{
            color: 'var(--text-muted)',
            fontSize: '0.8rem',
            transition: 'transform 0.2s ease',
            transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)',
          }}
        >
          ▲
        </span>
      </button>

      {/* Chunks list */}
      {!collapsed && (
        <div
          style={{
            padding: '0 24px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          {chunks.map((chunk, i) => (
            <ChunkCard key={chunk.chunk_id} chunk={chunk} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
